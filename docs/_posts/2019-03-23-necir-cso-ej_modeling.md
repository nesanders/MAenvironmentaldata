---
layout: post
title: Data analysis methodology for "Environmental justice implications of CSO outfall distribution"
ancillary: 1
---

{% raw %}
<script type="text/javascript" async
src="https://cdnjs.cloudflare.com/ajax/libs/mathjax/2.7.5/MathJax.js?config=TeX-MML-AM_CHTML">
</script>
{% endraw %}

This page explains the statistical methodologies underlying the analysis presented in ["Environmental justice implications of CSO outfall distribution"]({% post_url 2018-04-25-necir-cso-ej %}).

# Bootstrapping for visualization

We visualize the trend in CSO discharge volume by dividing the watersheds into four equal-sized bins according to each of the three EJ criteria defined by the state of Massachusetts and using [bootstrap resampling](https://en.wikipedia.org/wiki/Bootstrap_(statistics)) to estimate the uncertainty in the population-weighted mean discharge volume estimate in each bin.

# Regression modeling for dependence measurement

We measure the dependence of the CSO discharge outcome on EJ indicators using a Bayesian population-weighted logarithmic regression model as follows,

{% raw %}
<p>$$y \sim \textrm{N}(\theta, \sigma/\sqrt{p})$$</p>
<p>$$\theta = \alpha ~ x^{\beta}$$</p>
{% endraw %}

where *y* (dependent variable) is the annual volume of CSO discharge in gallons, *x* (independent variable) is the watershed-level EJ population indicator (linguistic isolation, income, or minority population) as a fraction, and *p* is the total population of Census blocks in the watershed. N is the [normal distribution](https://en.wikipedia.org/wiki/Normal_distribution) (defined such that the second argument is the standard deviation and not the variance). The parameter *&beta;* (the parameter whose inference this analysis is focused on) represents the univariate dependence of CSO discharge on each EJ indicator, *&alpha;* represents the offset (zero-point) between the dependent and independent variable, and *&sigma;* represents the noise or "error" in the dependent variable data.

We assign weakly informative priors (see e.g. [Sanders & Lei 2018](https://www.tandfonline.com/doi/full/10.1080/2330443X.2018.1448733)) to the parameters of this model as follows,

{% raw %}
<p>$$\sigma \sim \textrm{N}(0, 4)$$</p>
<p>$$\alpha \sim \textrm{N}(0, 10~\textrm{sd}(y))$$</p>
<p>$$\beta \sim \textrm{N}(0, 4)$$</p>
{% endraw %}

where sd is the standard deviation function.

The model is fit using the [pystan](https://mc-stan.org/) probabilistic programming language and inference tool using Hamiltonian Monte Carlo.  The exact Stan code for the model described above is available in the [{{ site.data.site_config.site_abbrev }} repository](https://github.com/nesanders/MAenvironmentaldata/blob/main/analysis/NECIR_CSO_map.py).

The plots below illustrate the functional form of the fitted model for each EJ indicator.  A sample of random draws from the Markov Chain posterior are shown in red.  The actual watershed data points are shown in blue, colored according to the watershed population used to weight the model fit.

![My helpful screenshot](/assets/figures/NECIR_CSO_stanfit_LINGISOPCT.png)
![My helpful screenshot](/assets/figures/NECIR_CSO_stanfit_LOWINCPCT.png)
![My helpful screenshot](/assets/figures/NECIR_CSO_stanfit_MINORPCT.png)

The plots below show the posterior probability distribution of the dependence measurement *&beta;* for each EH indicator, transformed as {% raw %}$$2^\beta$${% endraw %} to represent the growth of the dependent variable corresponding to a 2x increase in the independent variable.

![My helpful screenshot](/assets/figures/NECIR_CSO_stanfit_beta_LINGISOPCT.png)
![My helpful screenshot](/assets/figures/NECIR_CSO_stanfit_beta_LOWINCPCT.png)
![My helpful screenshot](/assets/figures/NECIR_CSO_stanfit_beta_MINORPCT.png)

The 90th percentile posterior (confidence) interval of these distributions are quoted in the analysis page.
