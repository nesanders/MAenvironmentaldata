---
layout: post
title: Modeling diagnostics for "Revisiting the environmental justice implications of CSOs with 2022 data"
ancillary: 1
---

This page provides modeling diagnostics for the analysis presented in [](). For an explaination of the statistical methodologies underlying the analysis, see ["Data analysis methodology for 'Environmental justice implications of CSO outfall distribution'"]({% post_url 2019-03-23-necir-cso-ej_modeling %}).

The plots below illustrate the functional form of the fitted model for each EJ indicator.  A sample of random draws from the Markov Chain posterior are shown in red.  The actual watershed data points are shown in blue, colored according to the watershed population used to weight the model fit.

![My helpful screenshot](/assets/figures/MAEEADP_CSO_stanfit_LINGISOPCT.png)
![My helpful screenshot](/assets/figures/MAEEADP_CSO_stanfit_LOWINCPCT.png)
![My helpful screenshot](/assets/figures/MAEEADP_CSO_stanfit_MINORPCT.png)

The plots below show the posterior probability distribution of the dependence measurement *&beta;* for each EH indicator, transformed as {% raw %}$$2^\beta$${% endraw %} to represent the growth of the dependent variable corresponding to a 2x increase in the independent variable.

![My helpful screenshot](/assets/figures/MAEEADP_CSO_stanfit_beta_LINGISOPCT.png)
![My helpful screenshot](/assets/figures/MAEEADP_CSO_stanfit_beta_LOWINCPCT.png)
![My helpful screenshot](/assets/figures/MAEEADP_CSO_stanfit_beta_MINORPCT.png)

The 90th percentile posterior (confidence) interval of these distributions are quoted in the analysis page.