use crate::MessageBuffer;
use pyo3::prelude::*;

#[pyclass(name = "MessageBuffer")]
pub struct PyMessageBuffer {
    inner: MessageBuffer,
}

#[pymethods]
impl PyMessageBuffer {
    #[new]
    #[pyo3(signature = (max_message_size = 10 * 1024 * 1024, max_buffer_size = 20 * 1024 * 1024))]
    pub fn new(max_message_size: usize, max_buffer_size: usize) -> Self {
        PyMessageBuffer {
            inner: MessageBuffer::with_config(max_message_size, max_buffer_size),
        }
    }

    pub fn add_data(&mut self, data: &[u8]) {
        self.inner.add_data(data);
    }

    pub fn extract_messages(&mut self) -> Vec<Vec<u8>> {
        self.inner.extract_messages()
    }

    pub fn clear(&mut self) {
        self.inner.clear();
    }

    pub fn is_empty(&self) -> bool {
        self.inner.is_empty()
    }

    fn __len__(&self) -> usize {
        self.inner.len()
    }
}

#[pymodule]
fn _message_buffer(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_class::<PyMessageBuffer>()?;
    Ok(())
}
