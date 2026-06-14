use crate::MessageBuffer;
use pyo3::exceptions::PyValueError;
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

#[pyfunction]
#[pyo3(signature = (type_code, content, request_id))]
fn compile(type_code: u16, content: &[u8], request_id: &[u8]) -> PyResult<Vec<u8>> {
    if request_id.len() != 4 {
        return Err(PyValueError::new_err("request_id must be exactly 4 bytes"));
    }
    let rid: [u8; 4] = request_id.try_into().unwrap();
    crate::protocol::compile(type_code, content, &rid)
        .map_err(|e| PyValueError::new_err(e.to_string()))
}

#[pyfunction]
#[pyo3(signature = (data, max_message_size = 10 * 1024 * 1024))]
fn parse(data: &[u8], max_message_size: usize) -> PyResult<(u16, Vec<u8>, [u8; 4], [u8; 4])> {
    let resp = crate::protocol::parse(data, max_message_size)
        .map_err(|e| PyValueError::new_err(e.to_string()))?;
    Ok((resp.type_code, resp.content, resp.hash, resp.request_id))
}

#[pymodule]
fn _message_buffer(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_class::<PyMessageBuffer>()?;
    m.add_function(wrap_pyfunction!(compile, m)?)?;
    m.add_function(wrap_pyfunction!(parse, m)?)?;
    Ok(())
}
