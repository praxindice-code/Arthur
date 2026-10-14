//! Local-only reference ingestion service. Put a reviewed HTTPS gateway in front
//! of this before connecting a published Roblox experience.
use bayesguard_detector::{roblox_event_index, RobloxDetector};
use std::collections::{HashMap, VecDeque};
use std::env;
use std::io::{Read, Write};
use std::net::{TcpListener, TcpStream};
use std::time::Duration;

const MAX_HEADER: usize = 8192;
const MAX_BODY: usize = 65536;
const MAX_SESSIONS: usize = 10000;
const MAX_ALERTS: usize = 1000;

#[repr(C)]
#[derive(Default)]
struct WindowCounts {
    movement: u32,
    remote: u32,
    reward: u32,
    timing: u32,
}

#[cfg(feature = "zig-window")]
unsafe extern "C" {
    fn bg_window_counts(events: *const u8, len: usize, out: *mut WindowCounts);
}

fn window_counts(events: &mut VecDeque<u8>) -> WindowCounts {
    let slice = events.make_contiguous();
    #[cfg(feature = "zig-window")]
    {
        let mut result = WindowCounts::default();
        // SAFETY: Zig reads exactly slice.len() bytes and writes one repr(C) struct.
        unsafe { bg_window_counts(slice.as_ptr(), slice.len(), &mut result); }
        result
    }
    #[cfg(not(feature = "zig-window"))]
    {
        let mut result = WindowCounts::default();
        for event in slice.iter().take(32) {
            match event {
                3 => result.movement += 1,
                4 => result.remote += 1,
                5 => result.reward += 1,
                6 => result.timing += 1,
                _ => {}
            }
        }
        result
    }
}

struct Session {
    detector: RobloxDetector,
    next_step: usize,
    recent: VecDeque<(usize, usize, f64, bool)>,
    window: VecDeque<u8>,
    alert_active: bool,
}

#[derive(Default)]
struct State {
    sessions: HashMap<String, Session>,
    alerts: VecDeque<String>,
}

fn valid_session(id: &str) -> bool {
    !id.is_empty() && id.len() <= 128 &&
        id.bytes().all(|b| b.is_ascii_alphanumeric() || matches!(b, b'-' | b'_' | b':' | b'.'))
}

fn parse_body(body: &str) -> Result<Vec<(String, usize, usize)>, &'static str> {
    let mut events = Vec::new();
    for line in body.lines() {
        if line.is_empty() { continue; }
        if events.len() >= 200 { return Err("too many events in batch"); }
        let mut fields = line.trim_end_matches('\r').split('\t');
        let id = fields.next().ok_or("missing session")?;
        let step = fields.next().ok_or("missing step")?
            .parse::<usize>().map_err(|_| "invalid step")?;
        let kind = fields.next().ok_or("missing kind")?;
        if fields.next().is_some() || !valid_session(id) { return Err("invalid event row"); }
        let event = roblox_event_index(kind).ok_or("unknown event kind")?;
        events.push((id.to_owned(), step, event));
    }
    if events.is_empty() { return Err("empty batch"); }
    Ok(events)
}

fn score_batch(state: &mut State, body: &str) -> Result<String, &'static str> {
    let events = parse_body(body)?;
    // Validate *all* steps before mutation: a bad batch cannot half-advance a session.
    let mut next: HashMap<&str, usize> = HashMap::new();
    for (id, step, event) in &events {
        let expected = next.get(id.as_str()).copied().unwrap_or_else(||
            state.sessions.get(id).map_or(*step, |session| session.next_step));
        if *step < expected {
            let cached = state.sessions.get(id).and_then(|session|
                session.recent.iter().find(|(cached_step, _, _, _)| cached_step == step));
            if !cached.is_some_and(|(_, cached_event, _, _)| cached_event == event) {
                return Err("conflicting or expired replay");
            }
        } else if *step == expected {
            next.insert(id, expected + 1);
        } else {
            return Err("step gap");
        }
    }
    if state.sessions.len() + next.keys().filter(|id| !state.sessions.contains_key(**id)).count()
        > MAX_SESSIONS { return Err("session capacity reached"); }
    let mut answer = String::new();
    for (id, step, event) in events {
        let session = state.sessions.entry(id.clone()).or_insert_with(|| Session {
            detector: RobloxDetector::new(0.5, 2), next_step: step,
            recent: VecDeque::new(), window: VecDeque::new(), alert_active: false,
        });
        if step < session.next_step {
            let (_, _, risk, alert) = session.recent.iter()
                .find(|(cached_step, cached_event, _, _)| *cached_step == step && *cached_event == event)
                .ok_or("expired replay")?;
            answer.push_str(&format!("{id}\t{step}\t{risk:.8}\t{}\n", u8::from(*alert)));
            continue;
        }
        let (risk, alert) = session.detector.update(event);
        session.next_step = step + 1;
        if session.window.len() == 32 { session.window.pop_front(); }
        session.window.push_back(event as u8);
        let counts = window_counts(&mut session.window);
        if session.recent.len() == 250 { session.recent.pop_front(); }
        session.recent.push_back((step, event, risk, alert));
        answer.push_str(&format!("{id}\t{step}\t{risk:.8}\t{}\n", u8::from(alert)));
        if alert && !session.alert_active {
            if state.alerts.len() == MAX_ALERTS { state.alerts.pop_front(); }
            state.alerts.push_back(format!("{id}\t{step}\t{risk:.8}\t{}\t{}\t{}\t{}",
                counts.movement, counts.remote, counts.reward, counts.timing));
        }
        session.alert_active = alert;
    }
    Ok(answer)
}

fn response(stream: &mut TcpStream, status: &str, body: &str) {
    let head = format!("HTTP/1.1 {status}\r\nContent-Type: text/plain; charset=utf-8\r\nContent-Length: {}\r\nConnection: close\r\nCache-Control: no-store\r\n\r\n", body.len());
    let _ = stream.write_all(head.as_bytes());
    let _ = stream.write_all(body.as_bytes());
}

fn read_request(stream: &mut TcpStream) -> Result<(String, String, Vec<(String, String)>, String), &'static str> {
    stream.set_read_timeout(Some(Duration::from_secs(5))).map_err(|_| "timeout setup failed")?;
    let mut raw = Vec::new();
    let mut chunk = [0u8; 4096];
    let header_end = loop {
        let count = stream.read(&mut chunk).map_err(|_| "request read failed")?;
        if count == 0 { return Err("incomplete request"); }
        raw.extend_from_slice(&chunk[..count]);
        if let Some(index) = raw.windows(4).position(|window| window == b"\r\n\r\n") {
            break index + 4;
        }
        if raw.len() > MAX_HEADER { return Err("headers too large"); }
    };
    if header_end > MAX_HEADER { return Err("headers too large"); }
    let header = std::str::from_utf8(&raw[..header_end]).map_err(|_| "invalid headers")?;
    let mut lines = header.split("\r\n");
    let first = lines.next().ok_or("missing request line")?;
    let mut request = first.split_whitespace();
    let method = request.next().ok_or("missing method")?.to_owned();
    let path = request.next().ok_or("missing path")?.to_owned();
    if request.next() != Some("HTTP/1.1") || request.next().is_some() {
        return Err("HTTP/1.1 required");
    }
    let headers: Vec<(String, String)> = lines.filter(|line| !line.is_empty()).map(|line| {
        line.split_once(':').map(|(name, value)| (name.trim().to_ascii_lowercase(), value.trim().to_owned()))
            .ok_or("malformed header")
    }).collect::<Result<_, _>>()?;
    let length_text = headers.iter().find(|(name, _)| name == "content-length")
        .map(|(_, value)| value.as_str()).unwrap_or("0");
    let length = length_text.parse::<usize>().map_err(|_| "invalid length")?;
    if length > MAX_BODY { return Err("body too large"); }
    while raw.len() - header_end < length {
        let count = stream.read(&mut chunk).map_err(|_| "body read failed")?;
        if count == 0 { return Err("incomplete body"); }
        raw.extend_from_slice(&chunk[..count]);
        if raw.len() - header_end > MAX_BODY { return Err("body too large"); }
    }
    let body = std::str::from_utf8(&raw[header_end..header_end + length])
        .map_err(|_| "invalid UTF-8 body")?.to_owned();
    Ok((method, path, headers, body))
}

fn handle(mut stream: TcpStream, key: &str, state: &mut State) {
    let (method, path, headers, body) = match read_request(&mut stream) {
        Ok(request) => request,
        Err(message) => { response(&mut stream, "400 Bad Request", message); return; }
    };
    if method == "GET" && path == "/health" {
        response(&mut stream, "200 OK", "ok\n");
        return;
    }
    let submitted = headers.iter().find(|(name, _)| name == "x-api-key")
        .map(|(_, value)| value.as_str()).unwrap_or("");
    if submitted.len() != key.len() ||
        submitted.bytes().zip(key.bytes()).fold(0u8, |acc, (a, b)| acc | (a ^ b)) != 0 {
        response(&mut stream, "401 Unauthorized", "unauthorized\n");
        return;
    }
    match (method.as_str(), path.as_str()) {
        ("POST", "/v1/events") => match score_batch(state, &body) {
            Ok(result) => response(&mut stream, "200 OK", &result),
            Err(message) => response(&mut stream, "400 Bad Request", message),
        },
        ("GET", "/v1/alerts") => {
            let mut result = state.alerts.iter().cloned().collect::<Vec<_>>().join("\n");
            if !result.is_empty() { result.push('\n'); }
            response(&mut stream, "200 OK", &result);
        }
        _ => response(&mut stream, "404 Not Found", "not found\n"),
    }
}

fn main() -> Result<(), Box<dyn std::error::Error>> {
    let key = env::var("BAYESGUARD_KEY")?;
    if key.len() < 16 || !key.bytes().all(|b| b.is_ascii_graphic()) {
        return Err("BAYESGUARD_KEY must be at least 16 printable ASCII characters".into());
    }
    let bind = env::var("BAYESGUARD_BIND").unwrap_or_else(|_| "127.0.0.1:8787".to_owned());
    if !bind.starts_with("127.0.0.1:") { return Err("local reference server must bind to 127.0.0.1".into()); }
    let listener = TcpListener::bind(&bind)?;
    println!("BayesGuard local reference server listening on {bind}");
    let mut state = State::default();
    for stream in listener.incoming() {
        match stream {
            Ok(stream) => handle(stream, &key, &mut state),
            Err(error) => eprintln!("connection error: {error}"),
        }
    }
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn batch_is_atomic_and_identical_replay_is_idempotent() {
        let mut state = State::default();
        assert!(score_batch(&mut state, "a\t0\taction_ok\na\t2\tremote_reject\n").is_err());
        assert!(state.sessions.is_empty());
        assert!(score_batch(&mut state, "a\t0\taction_ok\na\t1\tremote_reject\n").is_ok());
        assert!(score_batch(&mut state, "a\t1\tremote_reject\n").is_ok());
        assert!(score_batch(&mut state, "a\t1\treward_mismatch\n").is_err());
        assert_eq!(state.sessions["a"].next_step, 2);
    }

    #[test]
    fn invalid_kinds_and_session_ids_fail() {
        assert!(parse_body("a\t0\tclient_says_cheater\n").is_err());
        assert!(parse_body("a/b\t0\taction_ok\n").is_err());
    }

    #[test]
    fn bounded_window_features_count_each_signal() {
        let mut window = VecDeque::from([0, 3, 4, 5, 6, 3]);
        let counts = window_counts(&mut window);
        assert_eq!((counts.movement, counts.remote, counts.reward, counts.timing),
                   (2, 1, 1, 1));
    }
}
