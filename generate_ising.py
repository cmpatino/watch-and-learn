import sys
import h5py
from tqdm import tqdm
import jax.numpy as np
import numpy as onp

from jax import random, jit
from jax.ops import index, index_update
from typing import Iterator, Tuple, Callable

import hamiltonians

N = 8
T = 4.0
kb = 1.0
beta = 1/(kb*T)
Q = 2
flatten_pattern = "SPIRAL"


def create_grid(n_x: int, n_y: int) -> np.array:
    """Create a grid randomly filled with -1 and +1

    :param n_x: grid's first dimension
    :type n_x: int
    :param n_y: grids's second dimension
    :type n_y: int
    :return: grid of size (n_x, n_y)
    :rtype: np.array
    """
    key = random.PRNGKey(11)
    return random.randint(key, (n_x, n_y), 0, 2)*2 - 1


def flip_spin(grid: np.array, n_x: int, n_y: int) -> np.array:
    """Flip the spin of a single element on the grid

    :param grid: grid with spins
    :type grid: np.array
    :type n_x: int
    :param n_y: grids's second dimension
    :type n_y: int
    :return: grid with one flipped spin
    :rtype: np.array
    """

    key = random.PRNGKey(11)
    x = random.randint(key, (1, ), 0, n_x)
    y = random.randint(key, (1, ), 0, n_y)
    mask = index_update(np.ones_like(grid), index[x, y], -1)
    flipped_grid = grid*mask
    return flipped_grid


def metropolis(grid_curr: np.array, H_curr: float,
               H: Callable[[np.array], np.float32], C: float) -> Tuple[np.array, float]:
    """Metropolis update rule when flipping a single spin

    :param grid_curr: current grid
    :type grid_curr: np.array
    :param H_curr: current hamiltonian
    :type H_curr: float
    :param H: function to calculate Hamiltonian
    :type H: Callable[[np.array], np.float32]
    :param C: helper to calculate transition probability
    :type C: float
    :return: updated grid and Hamiltonian using Metropolis algorithm
    :rtype: Tuple[np.array, float]
    """

    n_x, n_y = grid_curr.shape
    grid_cand = jit(flip_spin, static_argnums=(1, 2))(grid_curr, n_x, n_y)
    H_cand = H(grid_cand)
    dH = H_cand - H_curr

    key = random.PRNGKey(11)
    alpha = random.uniform(key)
    if dH <= 0 or alpha < C**dH:
        H_curr = H_cand
        grid_curr = grid_cand

    return grid_curr, H_curr


def metropolis_chain(grid_curr: np.array, beta: float, H: Callable[[np.array], np.float32],
                     n_iter=0, burn_in=0) -> Iterator[np.array]:
    """Sample chain using Metropolis algorithm

    :param grid_curr: initial grid configuration
    :type grid_curr: np.array
    :param beta: inverse of Boltzmann's constant times the temperature
    :type beta: float
    :param H: function to calculate Hamiltonian
    :type H: Callable[[np.array], np.float32]
    :param n_iter: number of elements in chain, defaults to 0
    :type n_iter: int, optional
    :param burn_in: number of burn-in steps to help convergence, defaults to 0
    :type burn_in: int, optional
    :yield: chain of sampled states
    :rtype: Iterator[np.array]
    """

    C = np.exp(-beta)
    H_curr = H(grid_curr)
    n_x, n_y = grid_curr.shape
    grids = onp.zeros((n_iter, n_x, n_y))

    print(f"\nGenerating {burn_in} samples")
    for i in tqdm(range(burn_in)):
        grid_curr, H_curr = metropolis(grid_curr, H_curr, H, C)

    print(f"\nGenerating {n_iter} MC samples")
    for i in tqdm(range(n_iter)):
        grid_curr, H_curr = metropolis(grid_curr, H_curr, H, C)
        grids[i] = np.asarray(grid_curr, dtype=onp.int8)

    return grids


def h5gen(model="ISING1", n_samples=3200000,
          burn_in=110000, filename='training_data.hdf5') -> None:

    if model == "ISING1":
        H = hamiltonians.H_ising_1
    elif model == "ISING2":
        H = hamiltonians.H_ising_2

    grid_init = jit(create_grid, static_argnums=(0, 1))(N, N)
    grids = metropolis_chain(grid_init, beta, H, n_iter=n_samples, burn_in=burn_in)
    print('Generation of MC data is complete')

    with h5py.File(filename, "w") as f:
        f.create_dataset("ising_grids", data=grids, chunks=True)
    sys.stdout.flush()


if __name__ == "__main__":

    h5gen(n_samples=3200, burn_in=1100)
