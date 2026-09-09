use serde::Deserialize;
use std::{
    env, fs,
    io::{self, Read},
    process,
};

const MAX_NOTES_PER_MIDI_TRACK: usize = 16_000;

#[derive(Deserialize)]
struct Project {
    tempo: f64,
    ppq: u16,
    tracks: Vec<Track>,
}
#[derive(Deserialize)]
struct Track {
    channel: u8,
    notes: Vec<Note>,
}
#[derive(Deserialize)]
struct Note {
    start: u32,
    duration: u32,
    note: u8,
    velocity: u8,
}

fn variable_length(mut value: u32) -> Vec<u8> {
    let mut bytes = vec![value as u8 & 0x7f];
    while {
        value >>= 7;
        value != 0
    } {
        bytes.push((value as u8 & 0x7f) | 0x80);
    }
    bytes.reverse();
    for index in 0..bytes.len().saturating_sub(1) {
        bytes[index] |= 0x80;
    }
    bytes
}

fn track_bytes(track: &Track, notes: &[Note]) -> Vec<u8> {
    let mut events: Vec<(u32, bool, &Note)> =
        notes.iter().map(|note| (note.start, true, note)).collect();
    events.extend(
        notes
            .iter()
            .map(|note| (note.start + note.duration, false, note)),
    );
    events.sort_by_key(|(time, is_on, _)| (*time, !*is_on));
    let mut bytes = Vec::new();
    let mut cursor = 0;
    for (time, is_on, note) in events {
        bytes.extend(variable_length(time - cursor));
        bytes.extend([
            if is_on {
                0x90 | track.channel
            } else {
                0x80 | track.channel
            },
            note.note,
            if is_on { note.velocity } else { 0 },
        ]);
        cursor = time;
    }
    bytes.extend([0, 0xff, 0x2f, 0]);
    bytes
}

fn main() {
    let mut output = None;
    let mut args = env::args().skip(1);
    while let Some(argument) = args.next() {
        if argument == "--output" {
            output = args.next();
        }
    }
    let output = output.unwrap_or_else(|| {
        eprintln!("missing --output");
        process::exit(2);
    });
    let mut input = String::new();
    io::stdin()
        .read_to_string(&mut input)
        .unwrap_or_else(|error| {
            eprintln!("{error}");
            process::exit(1);
        });
    let project: Project = serde_json::from_str(&input).unwrap_or_else(|error| {
        eprintln!("invalid normalized project: {error}");
        process::exit(1);
    });
    let micros_per_quarter = (60_000_000.0 / project.tempo) as u32;
    let mut file = Vec::new();
    file.extend(b"MThd");
    file.extend(6u32.to_be_bytes());
    file.extend(1u16.to_be_bytes());
    file.extend((project.tracks.len() as u16 + 1).to_be_bytes());
    file.extend(project.ppq.to_be_bytes());
    let mut tempo_track = vec![
        0,
        0xff,
        0x51,
        3,
        (micros_per_quarter >> 16) as u8,
        (micros_per_quarter >> 8) as u8,
        micros_per_quarter as u8,
        0,
        0xff,
        0x2f,
        0,
    ];
    file.extend(b"MTrk");
    file.extend((tempo_track.len() as u32).to_be_bytes());
    file.append(&mut tempo_track);
    let mut note_count = 0;
    for track in &project.tracks {
        for notes in track.notes.chunks(MAX_NOTES_PER_MIDI_TRACK) {
            note_count += notes.len();
            let bytes = track_bytes(track, notes);
            file.extend(b"MTrk");
            file.extend((bytes.len() as u32).to_be_bytes());
            file.extend(bytes);
        }
    }
    fs::write(&output, file).unwrap_or_else(|error| {
        eprintln!("{error}");
        process::exit(1);
    });
    println!("wrote {note_count} notes to {output}");
}
