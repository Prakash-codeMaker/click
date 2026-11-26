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
    writer_opened = threading.Event()

    def write_fifo():
        with open(fifo_path, "wb") as stream:
            writer_opened.set()
            stream.write(b"fifo payload")

    writer = threading.Thread(target=write_fifo, daemon=True)
    writer.start()
    lazy_file = click.utils._LazyFile(fifo_path, mode="rb")

    try:
        # Construction must not open the FIFO: the writer should still be
        # waiting until the caller actually reads from the lazy file.
        assert not writer_opened.is_set()
        assert lazy_file.read() == b"fifo payload"
        writer.join(timeout=2)
        assert not writer.is_alive()
    finally:
        if writer.is_alive():
            # Unblock the writer if an assertion fails before the first read.
            fd = os.open(fifo_path, os.O_RDONLY | os.O_NONBLOCK)
            writer.join(timeout=2)
            os.close(fd)
        lazy_file.close()
