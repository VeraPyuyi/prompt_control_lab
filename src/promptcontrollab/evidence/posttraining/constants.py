"""Control-certificate policy names, schemas, and evidence levels."""

CONTROL_CERTIFICATES = {
    "terminal_sensitivity": "require_terminal_sensitivity",
    "green_certificate": "require_green_certificate",
    "posterior_certificate": "require_posterior_certificate",
}
CONTROL_CERTIFICATE_LEVELS = {
    "insufficient_evidence": 0,
    "not_applicable": 0,
    "empirical_only": 1,
    "surrogate_consistent": 2,
    "certificate_verified": 3,
}
MINIMUM_CONTROL_CERTIFICATE_LEVELS = {
    "empirical_only",
    "surrogate_consistent",
    "certificate_verified",
}
CONTROL_CERTIFICATE_SCHEMAS = {
    "terminal_sensitivity": "prompt_control_lab.terminal_sensitivity.v1",
    "green_certificate": "prompt_control_lab.green_certificate.v1",
    "posterior_certificate": "prompt_control_lab.posterior_certificate.v1",
}
CONTROL_CERTIFICATE_NATURAL_MAXIMUM = {
    "terminal_sensitivity": "empirical_only",
    "green_certificate": "certificate_verified",
    "posterior_certificate": "certificate_verified",
}
CONTROL_CERTIFICATE_STATES = {"passed", "conditions_not_met", "missing", "invalid"}
