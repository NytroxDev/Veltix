//! PyO3 bindings exposing the Veltix Rust protocol layer to Python.
//!
//! Thin wrapper around [`veltix_protocol`] and [`veltix_message_buffer`]:
//! no logic lives here, only the conversions between Rust types and Python
//! objects, so the Python package can call into the Rust implementations.
//!
//! The Python integration decides when to call this module (see the
//! `network.message_buffer` wrapper and the `VELTIX_DISABLE_RUST` escape
//! hatch); this crate is pure glue.

use pyo3::exceptions::PyValueError;
use pyo3::prelude::*;

use veltix_message_buffer::{
    AddDataOutcome, DEFAULT_MAX_BUFFER_SIZE, DropReason, ExtractItem,
    MessageBuffer as RustMessageBuffer,
};
use veltix_protocol::{compile as protocol_compile, parse as protocol_parse};

/// Decoded frame passed across the FFI boundary:
/// ``(type_code, content, request_id, flags, hash)``.
type ParsedFrame = (u16, Vec<u8>, u16, u8, Vec<u8>);

/// Parse a complete Veltix frame from *data* (magic, size and CRC32 checks).
///
/// Returns a [`ParsedFrame`] on success and raises ``ValueError`` when the
/// frame is invalid.
#[pyfunction]
pub fn parse(data: &[u8], max_message_size: usize) -> PyResult<ParsedFrame> {
    match protocol_parse(data, max_message_size) {
        Ok(resp) => Ok((
            resp.type_code,
            resp.content,
            resp.request_id,
            resp.flags,
            resp.hash.to_vec(),
        )),
        Err(error) => Err(PyValueError::new_err(error.to_string())),
    }
}

/// Serialize a message into wire format (15-byte header + content).
#[pyfunction]
pub fn compile(type_code: u16, content: &[u8], request_id: u16, flags: u8) -> PyResult<Vec<u8>> {
    protocol_compile(type_code, content, request_id, flags)
        .map_err(|error| PyValueError::new_err(error.to_string()))
}

/// Accumulates TCP stream data and extracts complete framed messages.
///
/// Mirrors `network.message_buffer.MessageBuffer` in Python.
#[pyclass]
pub struct MessageBuffer {
    inner: RustMessageBuffer,
}

#[pymethods]
impl MessageBuffer {
    /// Create a message buffer.
    ///
    /// Args:
    ///     max_message_size: Maximum allowed size of a single message.
    ///     max_buffer_size: Hard cap on total buffer growth (default 20 MiB).
    #[new]
    #[pyo3(signature = (max_message_size, max_buffer_size = DEFAULT_MAX_BUFFER_SIZE))]
    fn new(max_message_size: usize, max_buffer_size: usize) -> Self {
        Self {
            inner: RustMessageBuffer::with_config(max_message_size, max_buffer_size),
        }
    }

    /// Append raw bytes from the TCP stream.
    ///
    /// Returns ``(accepted, detail)``: *detail* is non-empty when the buffer
    /// limit was exceeded and the data was discarded (buffer cleared).
    fn add_data(&mut self, data: &[u8]) -> (bool, String) {
        match self.inner.add_data(data) {
            AddDataOutcome::Accepted => (true, String::new()),
            AddDataOutcome::Overflow { size, maximum } => (
                false,
                format!("Buffer size {size} exceeds maximum {maximum} - cleared"),
            ),
        }
    }

    /// Extract all complete messages as a list of tuples.
    ///
    /// Item shapes:
    ///     ("message", type_code, content, request_id, flags, hash)
    ///     ("dropped", kind, message)   kind: "too_large" | "parse_failed"
    ///     ("resynced", discarded)
    fn extract_messages(&mut self, py: Python<'_>) -> PyResult<Vec<(String, Py<PyAny>)>> {
        self.inner
            .extract_messages()
            .into_iter()
            .map(|item| {
                let entry = match item {
                    ExtractItem::Message(resp) => {
                        let payload = (
                            resp.type_code,
                            resp.content,
                            resp.request_id,
                            resp.flags,
                            resp.hash.to_vec(),
                        );
                        (
                            "message".to_string(),
                            payload.into_pyobject(py)?.into_any().unbind(),
                        )
                    }
                    ExtractItem::Dropped(reason) => {
                        let kind = match &reason {
                            DropReason::MessageTooLarge { .. } => "too_large",
                            DropReason::ParseFailed { .. } => "parse_failed",
                        };
                        let payload = (kind.to_string(), reason.to_string());
                        (
                            "dropped".to_string(),
                            payload.into_pyobject(py)?.into_any().unbind(),
                        )
                    }
                    ExtractItem::Resynced { discarded } => (
                        "resynced".to_string(),
                        discarded.into_pyobject(py)?.into_any().unbind(),
                    ),
                };
                Ok(entry)
            })
            .collect()
    }

    /// Discard all data currently held in the buffer.
    fn clear(&mut self) {
        self.inner.clear();
    }

    /// Number of bytes currently in the buffer.
    fn len(&self) -> usize {
        self.inner.len()
    }

    /// Number of bytes currently in the buffer (Python `len()` support).
    fn __len__(&self) -> usize {
        self.inner.len()
    }

    /// Maximum allowed size of a single message in bytes.
    #[getter]
    fn max_message_size(&self) -> usize {
        self.inner.max_message_size()
    }

    /// Hard cap on total buffer growth in bytes.
    #[getter]
    fn max_buffer_size(&self) -> usize {
        self.inner.max_buffer_size()
    }
}

/// Veltix Rust bindings module (imported as ``veltix._rust``).
#[pymodule]
#[pyo3(name = "_rust")]
fn veltix_bindings(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(parse, m)?)?;
    m.add_function(wrap_pyfunction!(compile, m)?)?;
    m.add_class::<MessageBuffer>()?;
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn parse_roundtrip() {
        let wire = protocol_compile(200, b"hello", 0x1234, 0).unwrap();
        let (type_code, content, request_id, flags, hash) = parse(&wire, 1024).unwrap();
        assert_eq!(type_code, 200);
        assert_eq!(content, b"hello");
        assert_eq!(request_id, 0x1234);
        assert_eq!(flags, 0);
        assert_eq!(hash, [0x36, 0x10, 0xA6, 0x86]); // crc32("hello"), from the wire vectors
    }

    #[test]
    fn compile_matches_protocol() {
        let wire = compile(200, b"hello", 0x1234, 0).unwrap();
        assert_eq!(wire, protocol_compile(200, b"hello", 0x1234, 0).unwrap());
    }
}
