# Third-Party Licenses

OCR Translator is built on top of the following open-source libraries.  
All copyright notices are reproduced as required by each respective license.

| Library                 | License                                     | Source                                                                 |
| ----------------------- | ------------------------------------------- | ---------------------------------------------------------------------- |
| Cython                  | Apache-2.0                                  | https://github.com/cython/cython/blob/master/LICENSE.txt              |
| deep-translator         | MIT                                         | https://github.com/nidhaloff/deep-translator/blob/master/LICENSE      |
| keyboard                | MIT                                         | https://github.com/boppreh/keyboard/blob/master/LICENSE.txt           |
| NumPy                   | BSD-3-Clause                                | https://numpy.org/doc/stable/license.html                             |
| PaddleOCR               | Apache-2.0                                  | https://github.com/PaddlePaddle/PaddleOCR/blob/main/LICENSE           |
| PaddlePaddle            | Apache-2.0                                  | https://github.com/PaddlePaddle/Paddle/blob/develop/LICENSE           |
| Pillow                  | MIT-CMU (HPND)                              | https://github.com/python-pillow/Pillow/blob/main/LICENSE             |
| PyInstaller             | GPL-2.0-or-later WITH Bootloader-exception  | https://pyinstaller.org/en/stable/license.html                        |
| PySide6                 | LGPLv3                                      | https://doc.qt.io/qtforpython-6/licenses.html                          |
| pystray                 | LGPLv3                                      | https://github.com/moses-palmer/pystray/blob/master/COPYING           |
| onnxruntime-directml    | MIT                                         | https://github.com/microsoft/onnxruntime/blob/main/LICENSE            |
| Hugging Face Hub        | Apache-2.0                                  | https://github.com/huggingface/huggingface_hub/blob/main/LICENSE      |
| PyYAML                  | MIT                                         | https://github.com/yaml/pyyaml/blob/master/LICENSE                     |
| pynvml                  | BSD-3-Clause                                | https://github.com/gpuopenanalytics/pynvml/blob/master/LICENSE        |

---

## Notes on LGPL libraries (PySide6, pystray)

These libraries are used **unmodified** and linked dynamically, in full compliance with LGPL requirements.  
Their source code is available at the official repositories listed above.  
Users may replace them with compatible versions as permitted by the LGPL.

## Notes on PyInstaller

PyInstaller is licensed under GPLv2 with a **Bootloader Exception**, which explicitly permits packaging and distributing programs under any license, including this project.  
For full details, see: https://pyinstaller.org/en/stable/license.html