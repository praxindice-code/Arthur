//! Online HMM inference for ordered, tab-separated audit event streams.
use std::env;
use std::error::Error;
use std::io::{self, BufRead};
use bayesguard_detector::{roblox_event_index, RobloxDetector};

const TRANSITIONS: [[f64; 5]; 5] = [
    [0.985, 0.015, 0.0, 0.0, 0.0],
    [0.12, 0.76, 0.12, 0.0, 0.0],
    [0.05, 0.05, 0.78, 0.12, 0.0],
    [0.03, 0.0, 0.05, 0.82, 0.10],
    [0.03, 0.0, 0.0, 0.02, 0.95],
];
const EMISSIONS: [[f64; 9]; 5] = [
    [0.27, 0.22, 0.28, 0.12, 0.04, 0.03, 0.02, 0.015, 0.005],
    [0.05, 0.12, 0.03, 0.01, 0.60, 0.14, 0.02, 0.02, 0.01],
    [0.03, 0.02, 0.01, 0.01, 0.10, 0.58, 0.15, 0.08, 0.02],
    [0.02, 0.04, 0.03, 0.01, 0.05, 0.05, 0.45, 0.30, 0.05],
    [0.01, 0.04, 0.15, 0.01, 0.02, 0.02, 0.03, 0.12, 0.60],
];

fn event_index(kind: &str) -> Option<usize> {
    match kind {
        "login_ok" => Some(0),
        "list_objects" => Some(1),
        "read_object" => Some(2),
        "logout" => Some(3),
        "list_users" => Some(4),
        "login_fail" => Some(5),
        "assume_role" => Some(6),
        "read_secret" => Some(7),
        "bulk_download" => Some(8),
        _ => None,
    }
}

struct Detector {
    posterior: [f64; 5],
    high_count: usize,
    threshold: f64,
    streak: usize,
}

impl Detector {
    fn new(threshold: f64, streak: usize) -> Self {
        Self { posterior: [1.0, 0.0, 0.0, 0.0, 0.0], high_count: 0, threshold, streak }
    }

    fn update(&mut self, event: usize) -> (f64, bool) {
        let mut weighted = [0.0; 5];
        for (next, value) in weighted.iter_mut().enumerate() {
            let predicted: f64 = (0..5)
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

fn main() -> Result<(), Box<dyn Error>> {
    let args: Vec<String> = env::args().collect();
    let (roblox, include_posterior, offset) = match args.as_slice() {
        [_, _, _] => (false, false, 0),
        [_, mode, _, _] if mode == "--roblox" => (true, false, 1),
        [_, mode, detail, _, _] if mode == "--roblox" && detail == "--posterior" =>
            (true, true, 2),
        _ => return Err("usage: bayesguard-detector [--roblox [--posterior]] <threshold> <streak> < events.tsv".into()),
    };
    let threshold: f64 = args[1 + offset].parse()?;
    let streak: usize = args[2 + offset].parse()?;
    if !(0.0 < threshold && threshold < 1.0) || streak == 0 {
        return Err("threshold must be in (0, 1); streak must be positive".into());
    }
    let mut detector = Detector::new(threshold, streak);
    let mut roblox_detector = RobloxDetector::new(threshold, streak);
    let mut current_session = String::new();
    let mut last_step: Option<usize> = None;
    for (line_number, line) in io::stdin().lock().lines().enumerate() {
        let line = line?;
        let parts: Vec<&str> = line.trim_end_matches('\r').split('\t').collect();
        if parts.len() != 3 || parts[0].is_empty() {
            return Err(format!("line {}: expected session_id, step, event_kind", line_number + 1).into());
        }
        let step: usize = parts[1].parse()?;
        let event = (if roblox { roblox_event_index(parts[2]) } else { event_index(parts[2]) })
            .ok_or_else(|| format!("line {}: unknown event kind", line_number + 1))?;
        if current_session != parts[0] {
            current_session = parts[0].to_string();
            detector = Detector::new(threshold, streak);
            roblox_detector = RobloxDetector::new(threshold, streak);
            last_step = None;
        }
        if last_step.is_some_and(|previous| step <= previous) {
            return Err(format!("line {}: steps must increase within a session", line_number + 1).into());
        }
        last_step = Some(step);
        let (risk, alert) = if roblox { roblox_detector.update(event) } else { detector.update(event) };
        if include_posterior {
            println!("{}\t{}\t{risk:.8}\t{}\t{:.8}\t{:.8}\t{:.8}\t{:.8}",
                parts[0], step, u8::from(alert),
                roblox_detector.posterior[0], roblox_detector.posterior[1],
                roblox_detector.posterior[2], roblox_detector.posterior[3]);
        } else {
            println!("{}\t{}\t{risk:.8}\t{}", parts[0], step, u8::from(alert));
        }
    }
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn attack_evidence_increases_risk() {
        let mut detector = Detector::new(0.7, 2);
        let normal = detector.update(event_index("login_ok").unwrap()).0;
        for event in ["list_users", "login_fail", "assume_role", "read_secret"] {
            detector.update(event_index(event).unwrap());
        }
        assert!(detector.update(event_index("bulk_download").unwrap()).0 > normal);
        let total: f64 = detector.posterior.iter().sum();
        assert!((total - 1.0).abs() < 1e-12);
    }

    #[test]
    fn roblox_evidence_increases_risk() {
        let mut detector = RobloxDetector::new(0.5, 2);
        let normal = detector.update(roblox_event_index("move_ok").unwrap()).0;
        for event in ["movement_violation", "remote_reject", "reward_mismatch"] {
            detector.update(roblox_event_index(event).unwrap());
        }
        assert!(detector.update(roblox_event_index("remote_reject").unwrap()).0 > normal);
        assert!((detector.posterior.iter().sum::<f64>() - 1.0).abs() < 1e-12);
    }
}
