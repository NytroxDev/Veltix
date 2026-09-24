//! Veltix message buffer — TCP stream framing with protocol hardening.
//!
//! Pure-Rust mirror of `src/veltix/network/message_buffer.py`. Accumulates
//! raw TCP stream data, extracts complete framed messages and recovers from
//! corruption by resynchronizing on the next MAGIC occurrence.
//!
//! Depends on [`veltix_protocol`] for the header layout and frame parsing:
//! whenever a candidate frame fails validation (MAGIC, size, CRC32) the
//! buffer drops it and resynchronizes, exactly like the Python
//! implementation.

use std::fmt;

use veltix_protocol::ProtocolError;

/// Default hard cap on total buffer growth in bytes (mirrors the Python
/// `MAX_BUFFER_SIZE` constant).
pub const DEFAULT_MAX_BUFFER_SIZE: usize = 20 * 1024 * 1024;

/// Outcome of [`MessageBuffer::add_data`].
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum AddDataOutcome {
    /// Data was appended to the buffer.
    Accepted,
    /// Appending would exceed `max_buffer_size`: the whole buffer was cleared
    /// and the incoming data discarded (mirrors the Python implementation,
    /// which never keeps the overflowing chunk).
    Overflow {
        /// Buffer size that would have resulted.
        size: usize,
        /// Configured maximum.
        maximum: usize,
    },
}

/// Reason a frame was dropped by [`MessageBuffer::extract_messages`].
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum DropReason {
    /// The frame's declared size exceeds `max_message_size`.
    MessageTooLarge {
        /// Declared frame size (header + content).
        size: usize,
        /// Configured maximum.
        maximum: usize,
    },
    /// The frame failed [`veltix_protocol::parse`] (e.g. CRC32 mismatch).
    ParseFailed {
        /// Size of the failed frame in bytes.
        len: usize,
        /// The underlying protocol error.
        error: ProtocolError,
    },
}

/// An item produced by [`MessageBuffer::extract_messages`].
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum ExtractItem {
    /// A fully validated frame (MAGIC, size and CRC32 all checked).
    Message(veltix_protocol::Response),
    /// A frame was dropped; the buffer then resynchronizes.
    Dropped(DropReason),
    /// Stream resynchronized: `discarded` bytes dropped, next MAGIC found.
    Resynced {
        /// Number of bytes discarded during resynchronization.
        discarded: usize,
    },
}

impl fmt::Display for DropReason {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            Self::MessageTooLarge { size, maximum } => {
                write!(f, "Message size {size} exceeds maximum {maximum}")
            }
            Self::ParseFailed { len, error } => {
                write!(f, "Failed to parse message ({len} bytes): {error}")
            }
        }
    }
}

/// Accumulates TCP stream data and extracts complete framed messages.
///
/// Buffers raw bytes until full frames are available, validates them through
/// [`veltix_protocol::parse`], and recovers from corrupted streams by
/// scanning forward for the next MAGIC occurrence.
pub struct MessageBuffer {
    data: Vec<u8>,
    max_message_size: usize,
    max_buffer_size: usize,
}

impl MessageBuffer {
    /// Create a buffer with the default 20 MiB buffer cap.
    ///
    /// Args:
    ///     max_message_size: Maximum allowed size of a single message.
    pub fn new(max_message_size: usize) -> Self {
        Self::with_config(max_message_size, DEFAULT_MAX_BUFFER_SIZE)
    }

    /// Create a buffer with explicit limits.
    ///
    /// Args:
    ///     max_message_size: Maximum allowed size of a single message.
    ///     max_buffer_size: Hard cap on total buffer growth in bytes.
    pub fn with_config(max_message_size: usize, max_buffer_size: usize) -> Self {
        MessageBuffer {
            data: Vec::new(),
            max_message_size,
            max_buffer_size,
        }
    }

    /// Append raw bytes from the TCP stream.
    ///
    /// If appending *data* would exceed `max_buffer_size`, the whole buffer
    /// is cleared and the data is discarded ([`AddDataOutcome::Overflow`]),
    /// matching the Python implementation.
    pub fn add_data(&mut self, data: &[u8]) -> AddDataOutcome {
        let size = self.data.len() + data.len();
        if size > self.max_buffer_size {
            self.clear();
            AddDataOutcome::Overflow {
                size,
                maximum: self.max_buffer_size,
            }
        } else {
            self.data.extend_from_slice(data);
            AddDataOutcome::Accepted
        }
    }

    /// Maximum allowed size of a single message in bytes.
    pub fn max_message_size(&self) -> usize {
        self.max_message_size
    }

    /// Hard cap on total buffer growth in bytes.
    pub fn max_buffer_size(&self) -> usize {
        self.max_buffer_size
    }

    /// Discard all data currently held in the buffer.
    pub fn clear(&mut self) {
        self.data.clear();
    }

    /// Number of bytes currently in the buffer.
    pub fn len(&self) -> usize {
        self.data.len()
    }

    /// Whether the buffer holds no data.
    pub fn is_empty(&self) -> bool {
        self.data.is_empty()
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use veltix_protocol::DEFAULT_MAX_MESSAGE_SIZE;

    #[test]
    fn starts_empty() {
        let buffer = MessageBuffer::new(DEFAULT_MAX_MESSAGE_SIZE);
        assert!(buffer.is_empty());
        assert_eq!(buffer.len(), 0);
    }

    #[test]
    fn add_data_grows_len() {
        let mut buffer = MessageBuffer::new(DEFAULT_MAX_MESSAGE_SIZE);
        buffer.add_data(&[0, 1, 2, 3]);
        assert_eq!(buffer.len(), 4);
    }

    #[test]
    fn overflow_discards_all_data() {
        let mut buffer = MessageBuffer::with_config(100, 100);
        assert_eq!(buffer.add_data(&[0x41; 80]), AddDataOutcome::Accepted);
        assert_eq!(buffer.len(), 80);

        let outcome = buffer.add_data(&[0x42; 200]);
        assert_eq!(
            outcome,
            AddDataOutcome::Overflow {
                size: 280,
                maximum: 100,
            }
        );
        assert!(buffer.is_empty());
    }

    #[test]
    fn overflow_edge_exactly_at_limit() {
        let mut buffer = MessageBuffer::with_config(100, 100);
        let outcome = buffer.add_data(&[0x41; 100]);
        assert_eq!(outcome, AddDataOutcome::Accepted);
        assert_eq!(buffer.len(), 100);
    }
}
