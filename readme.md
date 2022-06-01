![bnelearn-logo](docs/bnelearn-logo.png)

# A Framework for Equilibrium Learning in Sealed-Bid Auctions

[![pipeline status](https://gitlab.lrz.de/heidekrueger/bnelearn/badges/master/pipeline.svg)](https://gitlab.lrz.de/heidekrueger/bnelearn/commits/master) | [![coverage report](https://gitlab.lrz.de/heidekrueger/bnelearn/badges/master/coverage.svg)](https://gitlab.lrz.de/heidekrueger/bnelearn/commits/master)

bnelearn is a framework for equilibrium learning in sealed-bid auctions and other markets that can be modeled as Bayesian Games.

**Maintainers**: Stefan Heidekrüger ([@heidekrueger](https://github.com/heidekrueger)), Nils Kohring ([@kohring](https://github.com/kohring)), Markus Ewert ([@Markus-Ewert](https://github.com/Markus-Ewert)).

**Original Authors**: Stefan Heidekrüger, Paul Sutterer, Nils Kohring, Martin Bichler.

**Further Contributors**: Gleb Kilichenko ([@kilichenko](https://github.com/kilichenko)), Carina Fröhlich.


## What's Implemented?

Running experiments for $n$-player matrix and sealed-bid auction games with either

### Auctions and Other Games
* Single-item, multi-unit, LLG combinatorial auction, LLLLGG combinatorial auction.
* Priors and correlations: Uniform and normal priors that are either independent or Bernoulli or constant weight dependent. (Independent private values (IPV) and non-PV, e.g., common values.)
* Utility functions: Quasi-linear utility, either risk neutral, risk averse, or risk seeking.
* For combinatorial auctions: custom batched, cuda-enabled QP solver for quadratic auction rules + gurobi/cvxpy integration for arbitrary auctions stated as a MIP.
* Single-item auctions with first-, second-, and third-price rules, with known-BNE support for a wide range of settings.
* Local-Global combinatorial auctions, in particular LLG and LLLLGG
    * For LLG we support bne for independent and correlated local bidders for several core-selecting payment rules
* Split-award and mineral-rights auctions
* Tullock contest and crowd sourcing contest


### Algortihms
* Fictitious play, stochastic fictitious play, mixed fictitious play in matrix games.
* Neural self-play with directly computed policy gradients from [(Heinrich and Silver, 2016)](https://arxiv.org/abs/1603.01121), which is called ``PGLearner``.
* Neural pseudogradient ascent (NPGA), called ``ESPGLearner``, from [(Bichler et al., 2021)](https://www.nature.com/articles/s42256-021-00365-4).
* Particle swarm optimization (PSO), called ``PSOLearner``, from [(Kohring et al., 2022)](http://aaai-rlg.mlanctot.info/papers/AAAI22-RLG_paper_8.pdf).



## Where to Start?
* You can find the installation instructions at [Installation](docs/usage/installation).
* A quickstart guide is provided at [Quickstart](docs/usage/quickstart).
* Background information can be found under [Background](docs/usage/background).



## Contribute: Before Your First Commit
Please read [Contributing](contributing.md) carefully and follow the set-up steps described there.

**Git LFS**: On a new machine, please make sure you have git-lfs installed and configured for this repository. (See [contributing.md](contributing.md) for details.)


## Suggested Citation
If you find `bnelearn` helpful and use it in your work, please consider using the following citation:

```
@misc{Heidekrueger2021,
  author = {Heidekr\"uger, Stefan and Kohring, Nils and Sutterer, Paul and Bichler, Martin},
  title = {{bnelearn}: A Framework for Equilibrium Learning in Sealed-Bid Auctions},
  year = {2021},
  publisher = {GitHub},
  journal = {GitHub repository},
  howpublished = {\url{https://github.com/heidekrueger/bnelearn}}
}
```
