use std::fmt;

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum ProtocolError {
    TooShort { len: usize, minimum: usize },
    TooLarge { len: usize, maximum: usize },
    InvalidMagic { got: [u8; 2] },
    SizeMismatch { expected: usize, got: usize },
    HashMismatch,
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
                write!(f, "Invalid magic bytes: {got:02x?}")
            }
            Self::SizeMismatch { expected, got } => {
                write!(f, "Size mismatch: expected {expected} bytes, got {got}")
            }
            Self::HashMismatch => {
                write!(f, "Hash mismatch — corrupted data")
            }
            Self::ContentTooLarge { size, maximum } => {
                write!(f, "Content too large: {size} bytes (max: {maximum})")
            }
        }
    }
}

impl std::error::Error for ProtocolError {}
