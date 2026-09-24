//! Veltix wire protocol — framing constants and message (de)serialization.
//!
//! Pure-Rust mirror of `src/veltix/network/constants.py`, `request.py` and
//! `parser.py`. The wire format described here is the single source of truth
//! shared between the Python and Rust implementations.

/// Magic bytes identifying a Veltix frame.
pub const MAGIC: [u8; 2] = *b"VX";

/// Size of the request ID field in bytes.
pub const REQUEST_ID_SIZE: usize = 2;

// ── Header layout (15 bytes, big-endian) ──────────────────────────────────
//  Offset  Size  Field         Struct format
//  0       2     MAGIC         "2s"
//  2       1     flags         "B"
//  3       2     type code     "H"
//  5       4     content size  "I"
//  9       4     CRC32 hash    "4s"
//  13      2     request id    "2s"

pub const MAGIC_OFFSET: usize = 0;
pub const FLAGS_OFFSET: usize = 2;
pub const CODE_OFFSET: usize = 3;
pub const SIZE_OFFSET: usize = 5;
pub const HASH_OFFSET: usize = 9;
pub const REQUEST_ID_OFFSET: usize = 13;

/// Total header length in bytes.
pub const HEADER_SIZE: usize = REQUEST_ID_OFFSET + REQUEST_ID_SIZE;

/// Largest representable content size (uint32).
pub const MAX_CONTENT_SIZE: usize = u32::MAX as usize;

/// Default maximum accepted message size in bytes.
pub const DEFAULT_MAX_MESSAGE_SIZE: usize = 10 * 1024 * 1024;

/// A decoded Veltix frame.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Response {
    /// Protocol flags carried in the header.
    pub flags: u8,
    /// Message type code.
    pub type_code: u16,
    /// Raw content payload.
    pub content: Vec<u8>,
    /// CRC32 of the content as stored in the header.
    pub hash: [u8; 4],
    /// Request correlation ID.
    pub request_id: u16,
}
