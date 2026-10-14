//! Shared, deterministic Roblox event scoring core for replay and live ingestion.

const TRANSITIONS: [[f64; 4]; 4] = [
    [0.975, 0.010, 0.008, 0.007],
    [0.080, 0.870, 0.030, 0.020],
    [0.070, 0.020, 0.890, 0.020],
    [0.060, 0.020, 0.020, 0.900],
];
const EMISSIONS: [[f64; 7]; 4] = [
    [0.34, 0.36, 0.12, 0.05, 0.05, 0.04, 0.04],
    [0.08, 0.09, 0.08, 0.48, 0.12, 0.05, 0.10],
    [0.07, 0.08, 0.05, 0.11, 0.45, 0.18, 0.06],
    [0.08, 0.10, 0.04, 0.06, 0.12, 0.10, 0.50],
];

pub const EVENT_KINDS: [&str; 7] = [
    "move_ok", "action_ok", "latency_spike", "movement_violation",
    "remote_reject", "reward_mismatch", "repetitive_timing",
];

pub fn roblox_event_index(kind: &str) -> Option<usize> {
    EVENT_KINDS.iter().position(|candidate| *candidate == kind)
}

#[derive(Clone, Debug)]
pub struct RobloxDetector {
    pub posterior: [f64; 4],
    high_count: usize,
    threshold: f64,
    streak: usize,
}

impl RobloxDetector {
    pub fn new(threshold: f64, streak: usize) -> Self {
        Self { posterior: [1.0, 0.0, 0.0, 0.0], high_count: 0, threshold, streak }
    }

    pub fn update(&mut self, event: usize) -> (f64, bool) {
        assert!(event < EVENT_KINDS.len(), "invalid event index");
        let mut weighted = [0.0; 4];
        for (next, value) in weighted.iter_mut().enumerate() {
            let predicted: f64 = (0..4)
                .map(|previous| self.posterior[previous] * TRANSITIONS[previous][next])
                .sum();
            *value = predicted * EMISSIONS[next][event];
        }
        let total: f64 = weighted.iter().sum();
        for (next, value) in weighted.iter().enumerate() {
            self.posterior[next] = value / total;
        }
        let risk = 1.0 - self.posterior[0];
        self.high_count = if risk >= self.threshold { self.high_count + 1 } else { 0 };
        (risk, self.high_count >= self.streak)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn evidence_increases_risk_and_posterior_is_normalized() {
        let mut detector = RobloxDetector::new(0.5, 2);
        let normal = detector.update(roblox_event_index("move_ok").unwrap()).0;
        for kind in ["movement_violation", "remote_reject", "reward_mismatch"] {
            detector.update(roblox_event_index(kind).unwrap());
        }
        assert!(detector.update(roblox_event_index("remote_reject").unwrap()).0 > normal);
        assert!((detector.posterior.iter().sum::<f64>() - 1.0).abs() < 1e-12);
    }
}
