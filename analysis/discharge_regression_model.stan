// Power-law regression model: y ~ alpha * x^beta, weighted by population.
//
// Updated to current Stan best practices:
//   - inline variable initialization in transformed data / transformed parameters
//   - vectorized prediction using element-wise power operator .^  (no loop)
//   - pow() replaced by .^ throughout
data {
    int<lower=0> J;          // number of spatial units (watersheds / municipalities)
    vector<lower=0>[J] x;    // EJ parameter
    vector<lower=0>[J] y;    // CSO discharge
    vector<lower=0>[J] p;    // population (normalized)
}
transformed data {
    real s_y = sd(y);        // scale of outcome; used to set weakly informative priors
}
parameters {
    real<lower=0> alpha;     // multiplicative offset
    real beta;               // exponent
    real<lower=0> sigma;     // error model scaler
}
transformed parameters {
    vector[J] theta = alpha * (x .^ beta);   // vectorized power-law prediction
}
model {
    sigma ~ normal(0, 4);
    alpha ~ normal(0, 10 * s_y);
    beta  ~ normal(0, 4);
    y ~ normal(theta, sigma * s_y * sqrt(inv(p)));
}
