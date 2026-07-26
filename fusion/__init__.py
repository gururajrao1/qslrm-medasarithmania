"""fusion/ — fuse PV signals + omic risk + dose proxy; attribution shares."""

from fusion.scoring import FusionResult, fuse_risk, signal_strength, split_omic_attribution

__all__ = ["FusionResult", "fuse_risk", "split_omic_attribution", "signal_strength"]
