import pytest
from unittest.mock import MagicMock
from sim.pqspr import PQSPRegW, PQSPRegInc, PQSPRegTwiddle, PQSPRFile, TracePQSPR, Reg

@pytest.fixture
def mock_parent():
    """Creates a mock parent object."""
    return MagicMock()

@pytest.fixture
def pqsp_reg_w(mock_parent):
    """Creates an instance of PQSPRegW."""
    return PQSPRegW(mock_parent, idx=3, uval=0)

@pytest.fixture
def pqsp_reg_inc(mock_parent):
    """Creates an instance of PQSPRegInc."""
    return PQSPRegInc(mock_parent, idx=5, uval=0)

@pytest.fixture
def pqsp_reg_twiddle(mock_parent):
    """Creates an instance of PQSPRegTwiddle."""
    return PQSPRegTwiddle(mock_parent, idx=2, uval=0)

@pytest.fixture
def pqspr_file():
    """Creates an instance of PQSPRFile."""
    return PQSPRFile()

# Tests for PQSPRegW
def test_read_word_unsigned(pqsp_reg_w):
    pqsp_reg_w._uval = 0x12345678_9ABCDEF0_FEDCBA98_76543210
    assert pqsp_reg_w.read_word_unsigned(0) == 0x76543210
    assert pqsp_reg_w.read_word_unsigned(1) == 0xFEDCBA98
    assert pqsp_reg_w.read_word_unsigned(2) == 0x9ABCDEF0
    assert pqsp_reg_w.read_word_unsigned(3) == 0x12345678

def test_write_word_unsigned(pqsp_reg_w):
    pqsp_reg_w._uval = 0x12345678_9ABCDEF0_FEDCBA98_76543210
    
    pqsp_reg_w.write_word_unsigned(0xDEADBEEF, 0)
    assert pqsp_reg_w.read_word_unsigned(0) == 0x76543210
    pqsp_reg_w.commit()
    assert pqsp_reg_w.read_word_unsigned(0) == 0xDEADBEEF
    
    pqsp_reg_w.write_word_unsigned(0xBA5EBA11, 3)
    assert pqsp_reg_w.read_word_unsigned(3) == 0x12345678
    pqsp_reg_w.commit()
    assert pqsp_reg_w.read_word_unsigned(3) == 0xBA5EBA11
    
    pqsp_reg_w.write_word_unsigned(0x11223344, 6)
    assert pqsp_reg_w.read_word_unsigned(6) == 0x0
    pqsp_reg_w.commit()
    assert pqsp_reg_w.read_word_unsigned(6) == 0x11223344

def test_word_properties(pqsp_reg_w):
    pqsp_reg_w.B0 = 0x11223344
    assert pqsp_reg_w.B0 == 0x0
    pqsp_reg_w.commit()
    assert pqsp_reg_w.B0 == 0x11223344
    pqsp_reg_w.B7 = 0xAABBCCDD
    assert pqsp_reg_w.B7 == 0x0
    pqsp_reg_w.commit()
    assert pqsp_reg_w.B7 == 0xAABBCCDD

def test_invalid_word_index(pqsp_reg_w):
    with pytest.raises(AssertionError):
        pqsp_reg_w.read_word_unsigned(8)
    with pytest.raises(AssertionError):
        pqsp_reg_w._set_word(8, 0x12345678)

# Tests for PQSPRegInc
def test_increment(pqsp_reg_inc):
    pqsp_reg_inc._uval = 5
    pqsp_reg_inc.inc()
    assert pqsp_reg_inc._next_uval == 6
    pqsp_reg_inc.commit()
    assert pqsp_reg_inc._uval == 6
    assert pqsp_reg_inc.read_unsigned() == 6

def test_increment_overflow(pqsp_reg_inc):
    pqsp_reg_inc._uval = (1 << 32) - 1
    with pytest.raises(AssertionError):
        pqsp_reg_inc.inc()

# Tests for PQSPRegTwiddle
def test_set_as_psi(pqspr_file):
    pqspr_file.twiddle.write_unsigned(0x1234)
    pqspr_file.psi.write_unsigned(0x12345678_9ABCDEF0_FEDCBA98_76543210)
    pqspr_file.commit()
    assert pqspr_file.psi.B0 == 0x76543210
    
    pqspr_file.idx_psi.write_unsigned(1)
    pqspr_file.commit()
    assert pqspr_file.idx_psi.read_unsigned() == 1
    pqspr_file.twiddle.set_as_psi()
    pqspr_file.commit()
    assert pqspr_file.twiddle.read_unsigned() == 0xFEDCBA98

# Tests for PQSPRFile
def test_register_initialization(pqspr_file):
    assert pqspr_file.q._width == 32
    assert isinstance(pqspr_file.omega, PQSPRegW)
    assert isinstance(pqspr_file.idx_rc, PQSPRegInc)

def test_mark_written(pqspr_file):
    pqspr_file._pending_writes.clear()
    assert not pqspr_file._pending_writes
    
    pqspr_file.const.write_unsigned(0x1234567)
    assert 7 in pqspr_file._pending_writes
    
    pqspr_file.commit()
    assert not pqspr_file._pending_writes
    
    pqspr_file.idx_omega.inc()
    assert 5 in pqspr_file._pending_writes
    

def test_get_reg(pqspr_file):
    assert isinstance(pqspr_file.get_reg(3), PQSPRegW)

def test_commit(pqspr_file):
    pqspr_file.mark_written(3)
    pqspr_file.get_reg(3).commit = MagicMock()
    pqspr_file.commit()
    pqspr_file.get_reg(3).commit.assert_called_once()
    assert len(pqspr_file._pending_writes) == 0

def test_abort(pqspr_file):
    pqspr_file.mark_written(3)
    pqspr_file.get_reg(3).abort = MagicMock()
    pqspr_file.abort()
    pqspr_file.get_reg(3).abort.assert_called_once()
    assert len(pqspr_file._pending_writes) == 0
