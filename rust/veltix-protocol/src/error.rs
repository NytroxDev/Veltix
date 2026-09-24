//! Protocol-level errors produced by [`compile`](crate::compile) and [`parse`](crate::parse).

use std::fmt;

/// Errors raised while compiling or parsing Veltix frames.
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum ProtocolError {
    /// Input is shorter than the frame header.
    TooShort { len: usize, minimum: usize },
    /// Input exceeds the configured maximum message size.
    TooLarge { len: usize, maximum: usize },
    /// Frame does not start with the Veltix magic bytes.
    InvalidMagic { got: [u8; 2] },
    /// Content length differs from the size field stored in the header.
    SizeMismatch { expected: usize, got: usize },
    /// Content CRC32 does not match the hash stored in the header.
    HashMismatch,
    /// Content cannot be serialized because it exceeds 4 GiB.
    ContentTooLarge { size: usize, maximum: usize },
}

impl fmt::Display for ProtocolError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            Self::TooShort { len, minimum } => {
                write!(f, "Data too short: {len} bytes (minimum {minimum})")
            }
            Self::TooLarge { len, maximum } => {
                write!(f, "Message too large: {len} bytes (maximum {maximum})")
            }
            Self::InvalidMagic { got } => {
                write!(f, "Invalid magic bytes: {got:02X?}")
            }
            Self::SizeMismatch { expected, got } => {
                write!(f, "Size mismatch: expected {expected} bytes, got {got}")
            }
            Self::HashMismatch => {
                write!(f, "Hash mismatch : corrupted data")
            }
            Self::ContentTooLarge { size, maximum } => {
                write!(f, "Content too large: {size} bytes (max: {maximum})")
            }
        }
    }
}

impl std::error::Error for ProtocolError {}
