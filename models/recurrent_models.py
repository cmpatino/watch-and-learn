
import torch
from torch import nn
from torch.utils.data import DataLoader
import pytorch_lightning as pl

from data_utils.pytorch_datasets import IsingDataset


class ProbabilityRNN(pl.LightningModule):

    def __init__(self, hparams):
        super(ProbabilityRNN, self).__init__()
        if hparams.lstm:
            self.rnn = nn.LSTM(hparams.input_size, hparams.hidden_size,
                              num_layers=hparams.num_layers, batch_first=True)
        else:
            self.rnn = nn.GRU(hparams.input_size, hparams.hidden_size,
                              num_layers=hparams.num_layers, batch_first=True)
        self.linear = nn.Linear(hparams.hidden_size, hparams.output_size)
        self.train_datapath = hparams.train_datapath
        self.val_datapath = hparams.val_datapath
        self.test_datapath = hparams.test_datapath
        self.lr = hparams.lr
        self.batch_size = hparams.batch_size
        self.num_workers = hparams.num_workers
        self.beta = IsingDataset(filepath=self.train_datapath, data_key='beta').data
        self.avg_E = IsingDataset(filepath=self.train_datapath, data_key='avg_E').data

    def forward(self, x):
        x, _ = self.rnn(x)
        x = self.linear(x)

        return x

    def training_step(self, batch, batch_nb):
        x, y = batch
        y_hat = self(x)
        loss_fn = nn.BCEWithLogitsLoss()
        loss = loss_fn(y_hat, y)
        self.logger.experiment.add_scalar('train_loss', loss, self.trainer.global_step)
        return {'loss': loss}

    def validation_step(self, batch, batch_nb):
        # TODO: Implement metric for energy
        x, y = batch
        y_hat = self(x)
        loss_fn = nn.BCEWithLogitsLoss()
        loss = loss_fn(y_hat, y)
        return {'val_loss': loss}

    def validation_epoch_end(self, outputs):
        # TODO: Implement logger for energy difference
        avg_loss = torch.stack([x['val_loss'] for x in outputs]).mean()
        self.logger.experiment.add_scalar('val_loss', avg_loss, self.trainer.global_step)
        return {'avg_val_loss': avg_loss}

    def test_step(self, batch, batch_nb):
        x, y = batch
        y_hat = self(x)
        loss_fn = nn.BCEWithLogitsLoss()
        return {'test_loss': loss_fn(y_hat, y)}

    def test_epoch_end(self, outputs):
        avg_loss = torch.stack([x['test_loss'] for x in outputs]).mean()
        self.logger.experiment.add_scalar('test_loss', avg_loss, self.trainer.global_step)
        return {'avg_test_loss': avg_loss}

    def configure_optimizers(self):
        return torch.optim.Adam(self.parameters(), lr=self.lr)

    def train_dataloader(self):

        ising_dataset = IsingDataset(filepath=self.train_datapath, data_key='ising_grids')

        return DataLoader(ising_dataset, batch_size=self.batch_size,
                          num_workers=self.num_workers, shuffle=True)

    def val_dataloader(self):

        ising_dataset = IsingDataset(filepath=self.val_datapath, data_key='ising_grids')

        return DataLoader(ising_dataset, batch_size=self.batch_size)

    def test_dataloader(self):

        ising_dataset = IsingDataset(filepath=self.test_datapath, data_key='ising_grids')

        return DataLoader(ising_dataset, batch_size=self.batch_size)

    def calculate_probability(self, x, y):

        down_state_mask = (x == -1.)
        up_state_mask = (x == 1.)

        true_probs = torch.zeros_like(y)
        true_probs += (y*up_state_mask)
        true_probs += (down_state_mask.int() - y*down_state_mask)

        return torch.prod(true_probs, axis=1)

    def predict_energy(self, x):

        y_hat = torch.sigmoid(self(x))
        prob = self.calculate_probability(x, y_hat)
        H = (-1/torch.tensor(self.beta))*(torch.log(prob))

        return H
