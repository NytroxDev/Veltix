//! Veltix message buffer - TCP stream framing with protocol hardening.
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

use veltix_protocol::{parse, ProtocolError, HEADER_SIZE, MAGIC, SIZE_OFFSET};

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

/// Result of resynchronizing the read cursor after a corrupt frame.
enum ResyncFrom {
    /// Magic found; continue reading at the given index.
    Continue(usize),
    /// No magic found; buffer cleared.
    Cleared,
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

    /// Parse and return all complete framed messages currently in the buffer.
    ///
    /// Consumes as many complete messages as possible; partial messages
    /// remain buffered for the next call. When a frame fails validation
    /// (bad MAGIC, oversized, CRC32 mismatch) the buffer resynchronizes by
    /// scanning forward for the next MAGIC occurrence.
    ///
    /// Returns a list of [`ExtractItem`]s describing parsed messages, dropped
    /// frames, and resynchronization events so the caller can log them.
    pub fn extract_messages(&mut self) -> Vec<ExtractItem> {
        let mut items = Vec::new();
        let mut read = 0usize;

        loop {
            let avail = self.data.len() - read;
            if avail < HEADER_SIZE {
                break;
            }
            if &self.data[read..read + 2] != MAGIC.as_slice() {
                match self.resync_from(read, &mut items) {
                    ResyncFrom::Continue(idx) => read = idx,
                    ResyncFrom::Cleared => break,
                }
                continue;
            }
            let content_size = u32::from_be_bytes([
                self.data[read + SIZE_OFFSET],
                self.data[read + SIZE_OFFSET + 1],
                self.data[read + SIZE_OFFSET + 2],
                self.data[read + SIZE_OFFSET + 3],
            ]) as usize;
            let total_size = HEADER_SIZE + content_size;
            if total_size > self.max_message_size {
                items.push(ExtractItem::Dropped(DropReason::MessageTooLarge {
                    size: total_size,
                    maximum: self.max_message_size,
                }));
                match self.resync_from(read, &mut items) {
                    ResyncFrom::Continue(idx) => read = idx,
                    ResyncFrom::Cleared => break,
                }
                continue;
            }
            if avail < total_size {
                break;
            }
            match parse(&self.data[read..read + total_size], self.max_message_size) {
                Ok(response) => {
                    items.push(ExtractItem::Message(response));
                    read += total_size;
                }
                Err(error) => {
                    items.push(ExtractItem::Dropped(DropReason::ParseFailed {
                        len: total_size,
                        error,
                    }));
                    match self.resync_from(read, &mut items) {
                        ResyncFrom::Continue(idx) => read = idx,
                        ResyncFrom::Cleared => break,
                    }
                }
            }
        }

        // Compact the consumed prefix so the next add_data appends at offset
        // 0 and partial frames stay at the front of the buffer.
        if read >= self.data.len() {
            self.data.clear();
        } else if read > 0 {
            self.data.copy_within(read.., 0);
            self.data.truncate(self.data.len() - read);
        }

        items
    }

    /// Scan forward from `from + 1` for the next MAGIC occurrence.
    fn next_magic(&self, from: usize) -> Option<usize> {
        self.data[from + 1..]
            .windows(2)
            .position(|w| w == MAGIC.as_slice())
            .map(|offset| from + 1 + offset)
    }

    /// Resynchronize the read cursor after a corrupt frame.
    ///
    /// Mirrors the Python `_resync`: searches for the next MAGIC from `from
    /// + 1` and either discards up to it ([`ResyncFrom::Continue`], emitting
    /// a [`ExtractItem::Resynced`] for logging) or clears the whole buffer
    /// silently ([`ResyncFrom::Cleared`]).
    fn resync_from(&mut self, from: usize, items: &mut Vec<ExtractItem>) -> ResyncFrom {
        match self.next_magic(from) {
            Some(idx) => {
                items.push(ExtractItem::Resynced {
                    discarded: idx - from,
                });
                ResyncFrom::Continue(idx)
            }
            None => {
                self.clear();
                ResyncFrom::Cleared
            }
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use veltix_protocol::{ProtocolError, DEFAULT_MAX_MESSAGE_SIZE};

    /// Decode a frame from its hexadecimal representation.
    fn hex(s: &str) -> Vec<u8> {
        (0..s.len())
            .step_by(2)
            .map(|i| u8::from_str_radix(&s[i..i + 2], 16).unwrap())
            .collect()
    }

    // Well-known frames mirrored from tests/protocol_vectors.py (Python).
    const HELLO: &str = "56580000c8000000053610a686123468656c6c6f";
    const EMPTY: &str = "565800000000000000000000000000";
    const UTF8: &str = "56580000c90000000b035d5cdeffff56656c74697820f09fa680";
    const PLUGIN_JSON: &str = "565800271000000010d2e71e5100017b226b223a205b312c20322c20335d7d";

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

    #[test]
    fn extracts_single_message() {
        let mut buffer = MessageBuffer::new(DEFAULT_MAX_MESSAGE_SIZE);
        buffer.add_data(&hex(HELLO));
        let items = buffer.extract_messages();
        assert_eq!(items.len(), 1);
        match &items[0] {
            ExtractItem::Message(resp) => {
                assert_eq!(resp.type_code, 200);
                assert_eq!(resp.content, b"hello");
                assert_eq!(resp.request_id, 0x1234);
            }
            other => panic!("expected Message, got {other:?}"),
        }
        assert!(buffer.is_empty());
    }

    #[test]
    fn extracts_empty_content_message() {
        let mut buffer = MessageBuffer::new(DEFAULT_MAX_MESSAGE_SIZE);
        buffer.add_data(&hex(EMPTY));
        let items = buffer.extract_messages();
        assert_eq!(items.len(), 1);
        match &items[0] {
            ExtractItem::Message(resp) => {
                assert_eq!(resp.type_code, 0);
                assert!(resp.content.is_empty());
            }
            other => panic!("expected Message, got {other:?}"),
        }
    }

    #[test]
    fn extracts_two_concatenated_messages() {
        let mut buffer = MessageBuffer::new(DEFAULT_MAX_MESSAGE_SIZE);
        let mut stream = hex(HELLO);
        stream.extend_from_slice(&hex(PLUGIN_JSON));
        buffer.add_data(&stream);
        let items = buffer.extract_messages();
        assert_eq!(items.len(), 2);
        match (&items[0], &items[1]) {
            (ExtractItem::Message(a), ExtractItem::Message(b)) => {
                assert_eq!(a.content, b"hello");
                assert_eq!(b.type_code, 10000);
                assert_eq!(b.content, br#"{"k": [1, 2, 3]}"#);
            }
            other => panic!("expected two Messages, got {other:?}"),
        }
        assert!(buffer.is_empty());
    }

    #[test]
    fn partial_header_preserved() {
        let mut buffer = MessageBuffer::new(DEFAULT_MAX_MESSAGE_SIZE);
        buffer.add_data(&hex(HELLO)[..4]);
        let items = buffer.extract_messages();
        assert!(items.is_empty());
        assert_eq!(buffer.len(), 4);
    }

    #[test]
    fn partial_content_preserved() {
        let mut buffer = MessageBuffer::new(DEFAULT_MAX_MESSAGE_SIZE);
        buffer.add_data(&hex(HELLO)[..18]); // 15 header + 3 of 5 content
        let items = buffer.extract_messages();
        assert!(items.is_empty());
        assert_eq!(buffer.len(), 18);
    }

    #[test]
    fn split_message_across_adds() {
        let mut buffer = MessageBuffer::new(DEFAULT_MAX_MESSAGE_SIZE);
        let wire = hex(HELLO);
        buffer.add_data(&wire[..wire.len() / 2]);
        assert!(buffer.extract_messages().is_empty());
        buffer.add_data(&wire[wire.len() / 2..]);
        let items = buffer.extract_messages();
        assert_eq!(items.len(), 1);
        assert!(matches!(&items[0], ExtractItem::Message(_)));
        assert!(buffer.is_empty());
    }

    #[test]
    fn leftover_partial_preserved_after_extraction() {
        let mut buffer = MessageBuffer::new(DEFAULT_MAX_MESSAGE_SIZE);
        let mut stream = hex(HELLO);
        let plugin = hex(PLUGIN_JSON);
        stream.extend_from_slice(&plugin[..10]); // partial second frame
        buffer.add_data(&stream);
        let items = buffer.extract_messages();
        assert_eq!(items.len(), 1);
        assert!(matches!(&items[0], ExtractItem::Message(_)));
        assert_eq!(buffer.len(), 10);

        buffer.add_data(&plugin[10..]);
        let items = buffer.extract_messages();
        assert_eq!(items.len(), 1);
        match &items[0] {
            ExtractItem::Message(resp) => assert_eq!(resp.type_code, 10000),
            other => panic!("expected Message, got {other:?}"),
        }
        assert!(buffer.is_empty());
    }

    #[test]
    fn garbage_before_valid_frame() {
        let mut buffer = MessageBuffer::new(DEFAULT_MAX_MESSAGE_SIZE);
        let mut stream = vec![0x00, 0x01, 0x02, 0x03, 0x04, 0x05, 0x06, 0x07, 0x08, 0x09];
        stream.extend_from_slice(&hex(HELLO));
        buffer.add_data(&stream);
        let items = buffer.extract_messages();
        assert_eq!(items.len(), 2);
        assert!(matches!(&items[0], ExtractItem::Resynced { discarded: 10 }));
        assert!(matches!(&items[1], ExtractItem::Message(_)));
        assert!(buffer.is_empty());
    }

    #[test]
    fn corrupted_magic_then_valid() {
        let mut buffer = MessageBuffer::new(DEFAULT_MAX_MESSAGE_SIZE);
        let mut corrupt = hex(HELLO);
        corrupt[0] = 0x00;
        corrupt[1] = 0x00;
        corrupt.extend_from_slice(&hex(PLUGIN_JSON));
        buffer.add_data(&corrupt);
        let items = buffer.extract_messages();
        assert_eq!(items.len(), 2);
        assert!(matches!(&items[0], ExtractItem::Resynced { discarded: 20 }));
        assert!(matches!(&items[1], ExtractItem::Message(_)));
        assert!(buffer.is_empty());
    }

    #[test]
    fn corrupt_frame_then_valid() {
        let mut buffer = MessageBuffer::new(DEFAULT_MAX_MESSAGE_SIZE);
        let mut corrupt = hex(HELLO);
        let last = corrupt.len() - 1;
        corrupt[last] ^= 0xFF; // corrupt content -> CRC32 mismatch
        corrupt.extend_from_slice(&hex(PLUGIN_JSON));
        buffer.add_data(&corrupt);
        let items = buffer.extract_messages();
        assert_eq!(items.len(), 3); // Dropped + Resynced + Message
        match (&items[0], &items[1], &items[2]) {
            (
                ExtractItem::Dropped(DropReason::ParseFailed { len, error }),
                ExtractItem::Resynced { discarded: 20 },
                ExtractItem::Message(_),
            ) => {
                assert_eq!(*len, 20);
                assert_eq!(*error, ProtocolError::HashMismatch);
            }
            other => panic!("unexpected items: {other:?}"),
        }
        assert!(buffer.is_empty());
    }

    #[test]
    fn size_exceeds_max_resyncs() {
        let mut buffer = MessageBuffer::with_config(50, DEFAULT_MAX_BUFFER_SIZE);
        let mut oversized = hex(HELLO);
        oversized[5..9].copy_from_slice(&100u32.to_be_bytes()); // declares 100 content bytes
        buffer.add_data(&oversized);
        let items = buffer.extract_messages();
        assert_eq!(items.len(), 1);
        assert!(matches!(
            &items[0],
            ExtractItem::Dropped(DropReason::MessageTooLarge {
                size: 115,
                maximum: 50
            })
        ));
        // No further MAGIC in the buffer: silently cleared.
        assert!(buffer.is_empty());
    }

    #[test]
    fn corrupted_size_field_then_valid() {
        let mut buffer = MessageBuffer::new(DEFAULT_MAX_MESSAGE_SIZE);
        let mut oversized = hex(HELLO);
        oversized[5] = 0xFF; // corrupt size high byte (mirrors Python test)
        oversized.extend_from_slice(&hex(PLUGIN_JSON));
        buffer.add_data(&oversized);
        let items = buffer.extract_messages();
        assert_eq!(items.len(), 3);
        assert!(matches!(
            &items[0],
            ExtractItem::Dropped(DropReason::MessageTooLarge { .. })
        ));
        assert!(matches!(&items[1], ExtractItem::Resynced { discarded: 20 }));
        assert!(matches!(&items[2], ExtractItem::Message(_)));
        assert!(buffer.is_empty());
    }

    #[test]
    fn no_magic_found_clears_buffer() {
        let mut buffer = MessageBuffer::new(DEFAULT_MAX_MESSAGE_SIZE);
        let garbage: Vec<u8> = (0..18u8).collect();
        buffer.add_data(&garbage);
        let items = buffer.extract_messages();
        // Silent clear: no Resynced item is emitted when MAGIC is not found.
        assert!(items.is_empty());
        assert!(buffer.is_empty());
    }

    #[test]
    fn continuous_garbage_stream_does_not_grow() {
        let mut buffer = MessageBuffer::new(DEFAULT_MAX_MESSAGE_SIZE);
        let garbage: Vec<u8> = (0..18u8).collect();
        for _ in 0..10 {
            buffer.add_data(&garbage);
            let items = buffer.extract_messages();
            assert!(items.is_empty());
            assert!(buffer.is_empty());
        }
    }

    #[test]
    fn extract_after_drain_is_empty() {
        let mut buffer = MessageBuffer::new(DEFAULT_MAX_MESSAGE_SIZE);
        buffer.add_data(&hex(HELLO));
        assert_eq!(buffer.extract_messages().len(), 1);
        assert!(buffer.extract_messages().is_empty());
    }

    #[test]
    fn roundtrip_utf8_message() {
        let mut buffer = MessageBuffer::new(DEFAULT_MAX_MESSAGE_SIZE);
        buffer.add_data(&hex(UTF8));
        let items = buffer.extract_messages();
        assert_eq!(items.len(), 1);
        match &items[0] {
            ExtractItem::Message(resp) => {
                assert_eq!(resp.type_code, 201);
                assert_eq!(resp.content, "Veltix 🦀".as_bytes());
                assert_eq!(resp.request_id, 0xFFFF);
            }
            other => panic!("expected Message, got {other:?}"),
        }
    }
}
