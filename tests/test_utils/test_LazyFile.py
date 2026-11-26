import os
import threading

import click
import pytest


def test_iter_lazyfile(tmpdir):
    expected = list(map(str, range(10)))
    p = tmpdir.mkdir("testdir").join("testfile")
    p.write("\n".join(expected))
    with p.open() as f:
        with click.utils._LazyFile(f.name) as lf:
            for e_line, a_line in zip(expected, lf, strict=False):
                assert e_line == a_line.strip()

@pytest.mark.skipif(not hasattr(os, "mkfifo"), reason="Named pipes require POSIX")
def test_lazy_file_does_not_consume_fifo_before_first_read(tmp_path):
    fifo_path = tmp_path / "input.fifo"
    os.mkfifo(fifo_path)
    constructed = threading.Event()
    lazy_files = []

    def construct_lazy_file():
        lazy_files.append(click.utils._LazyFile(fifo_path, mode="rb"))
        constructed.set()

    constructor = threading.Thread(target=construct_lazy_file, daemon=True)
    constructor.start()

    if not constructed.wait(timeout=2):
        # Release an eager FIFO open on the old implementation so this test
        # fails cleanly instead of leaving a blocked daemon thread behind.
        with open(fifo_path, "wb", buffering=0):
            pass
        constructor.join(timeout=2)
        pytest.fail("LazyFile eagerly opened the FIFO during construction")

    lazy_file = lazy_files[0]

    def write_fifo():
        with open(fifo_path, "wb") as stream:
            stream.write(b"fifo payload")

    writer = threading.Thread(target=write_fifo, daemon=True)
    writer.start()

    try:
        assert lazy_file.read() == b"fifo payload"
        writer.join(timeout=2)
        assert not writer.is_alive()
    finally:
        lazy_file.close()
