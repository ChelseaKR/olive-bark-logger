# Recording-Law Notes — why level-only

**Last verified: 2026-06-05 · Recheck cadence: per recording-law review.**
**This is engineering rationale, not legal advice. Consult a lawyer for your jurisdiction.**

## The concern

Many jurisdictions regulate *recording* of conversations — "two-party" / "all-party"
consent statutes and wiretap/eavesdropping laws. A device left running in a home that
captured audio could plausibly record household members, guests, or sound carrying from
a neighbor, raising consent and eavesdropping questions and creating a sensitive
artifact that could be subpoenaed, leaked, or misused.

## The design answer

This tool **measures sound levels and event metadata only, and never captures, stores,
or transmits audio** (see [`no-audio-guarantee.md`](./no-audio-guarantee.md)). A dBFS
level computed in memory and immediately discarded is not a recording of a conversation:
no speech is retained, nothing is intelligible, and there is no artifact from which
content could ever be reconstructed. By removing recording entirely:

- There is no captured conversation to which consent law could attach.
- There is nothing to wiretap, subpoena, or leak — the artifact does not exist.
- The evidentiary value we actually need ("it was loud, here, at these times, for this
  long") is preserved without the content that creates legal and ethical exposure.

This posture is kept front-and-center in the README, the report's Methodology and
Limitations sections, and the data model itself.

## What this does *not* claim

- It does not claim legal compliance in any specific jurisdiction; local law varies.
- It does not claim to identify a sound's source (see methodology limitations).
- It is not a courtroom-grade SPL meter.

The honest framing — informational, not adversarial — is itself part of the compliance
posture: the tool is built to inform a dispute, never to manufacture one.
