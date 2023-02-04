data {
    int<lower=0> J;         // number of watersheds
    vector<lower=0>[J] x;   // EJ parameter
    vector<lower=0>[J] y;   // CSO discharge
    vector<lower=0>[J] p;   // population (normalized)
}
transformed data {
    real<lower=0> s_y;
    
    s_y = sd(y);
}
parameters {
    real<lower=0> alpha;    // Multiplicative offset
    real beta;              // Exponent
    real<lower=0> sigma;    // Error model scaler
}
transformed parameters {
    vector[J] theta;        // Regression estimate
    
    for (i in 1:J) {
        theta[i] = alpha * pow(x[i], beta);
    }
}
model {
    sigma ~ normal(0, 4);
    alpha ~ normal(0, 10*s_y);
    beta ~ normal(0, 4);
    y ~ normal(theta, sigma * s_y * sqrt(inv(p)));
}
