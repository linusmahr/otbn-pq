import pytest
from unittest.mock import MagicMock
from sim.pqspr import PQSPRegInc, PQSPRegTwiddle, PQSPRFile, TracePQSPR, Reg, PQSPRegOmega

@pytest.fixture
def mock_parent():
    """Creates a mock parent object."""
    return MagicMock()

@pytest.fixture
def pqsp_reg_w(mock_parent):
    """Creates an instance of wide Register."""
    return Reg(mock_parent, idx=3, width=256, uval=0)

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
    return PQSPRFile('p')

# Tests for Reg extension
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

# Tests for PQSPRFile
def test_register_initialization(pqspr_file):
    assert pqspr_file.q._width == 32
    assert isinstance(pqspr_file.omega, PQSPRegOmega)
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
    assert isinstance(pqspr_file.get_reg(3), PQSPRegOmega)

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

# Tests for PQSPRegTwiddle
def test_twiddle_set_as_psi(pqspr_file):
    pqspr_file.twiddle.write_unsigned(0x1234)
    pqspr_file.psi.write_unsigned(0x12345678_9ABCDEF0_FEDCBA98_76543210)
    pqspr_file.commit()
    assert pqspr_file.psi.read_word_unsigned(0) == 0x76543210
    
    pqspr_file.idx_psi.write_unsigned(1)
    pqspr_file.commit()
    assert pqspr_file.idx_psi.read_unsigned() == 1
    pqspr_file.twiddle.set_as_psi()
    pqspr_file.commit()
    assert pqspr_file.twiddle.read_unsigned() == 0xFEDCBA98
    
def test_twiddle_update1(pqspr_file):
    # test 1
    pqspr_file.wipe()
    pqspr_file.commit()
    
    pqspr_file.omega.write_unsigned(0x1234)
    pqspr_file.q.write_unsigned(0xD01)
    pqspr_file.q_dash.write_unsigned(0x94570cff)
    pqspr_file.twiddle.write_unsigned(0x2)
    pqspr_file.commit()
    
    assert pqspr_file.twiddle._next_uval == None
    pqspr_file.twiddle.update()
    pqspr_file.twiddle.commit()
    assert pqspr_file.twiddle.read_unsigned() == 0x690
    
def test_twiddle_update2(pqspr_file):
    # test 2
    pqspr_file.wipe()
    pqspr_file.commit()
    
    pqspr_file.omega.write_unsigned(0x01234567)
    pqspr_file.q.write_unsigned(0xD01)
    pqspr_file.q_dash.write_unsigned(0x94570cff)
    pqspr_file.twiddle.write_unsigned(0x89abcdef)
    pqspr_file.commit()
    
    assert pqspr_file.twiddle._next_uval == None
    pqspr_file.twiddle.update()
    pqspr_file.twiddle.commit()
    assert pqspr_file.twiddle.read_unsigned() == 0x9CA02C
    
def test_twiddle_invert1(pqspr_file):
    # test 1
    pqspr_file.wipe()
    pqspr_file.commit()
    
    pqspr_file.q.write_unsigned(0x55)
    pqspr_file.twiddle.write_unsigned(0x22)
    pqspr_file.commit()
    
    assert pqspr_file.twiddle._next_uval == None
    pqspr_file.twiddle.inv()
    pqspr_file.twiddle.commit()
    assert pqspr_file.twiddle.read_unsigned() == 0x33
    
def test_twiddle_invert2(pqspr_file):
    # test 2
    pqspr_file.wipe()
    pqspr_file.commit()
    
    pqspr_file.q.write_unsigned(0xdeadbeef)
    pqspr_file.twiddle.write_unsigned(0x76543210)
    pqspr_file.commit()
    
    assert pqspr_file.twiddle._next_uval == None
    pqspr_file.twiddle.inv()
    pqspr_file.twiddle.commit()
    assert pqspr_file.twiddle.read_unsigned() == 0x68598CDF
    
def test_twiddle_mark_written(pqspr_file):
    pqspr_file._pending_writes.clear()
    assert not pqspr_file._pending_writes
    pqspr_file.twiddle.update()
    assert 2 in pqspr_file._pending_writes
    pqspr_file.commit()
    assert not pqspr_file._pending_writes
    
    pqspr_file._pending_writes.clear()
    assert not pqspr_file._pending_writes
    pqspr_file.twiddle.inv()
    assert 2 in pqspr_file._pending_writes
    pqspr_file.commit()
    assert not pqspr_file._pending_writes
    
    pqspr_file._pending_writes.clear()
    assert not pqspr_file._pending_writes
    pqspr_file.twiddle.set_as_psi()
    assert 2 in pqspr_file._pending_writes
    pqspr_file.commit()
    assert not pqspr_file._pending_writes
    
    
def test_omega_update1(pqspr_file):
    # test 1
    pqspr_file.omega.write_unsigned(0x1234)
    pqspr_file.q.write_unsigned(0xD01)
    pqspr_file.q_dash.write_unsigned(0x94570cff)
    pqspr_file.commit()
    
    assert pqspr_file.omega._next_uval == None
    pqspr_file.omega.update()
    pqspr_file.omega.commit()
    assert pqspr_file.omega.read_unsigned() == 0xb09
    
def test_omega_update2(pqspr_file):
    # test 2
    pqspr_file.omega.write_unsigned(0xdeadbeef)
    pqspr_file.q.write_unsigned(0xD01)
    pqspr_file.q_dash.write_unsigned(0x94570cff)
    pqspr_file.commit()
    
    assert pqspr_file.omega._next_uval == None
    pqspr_file.omega.update()
    assert pqspr_file.omega._uval == 0xdeadbeef
    assert pqspr_file.omega._next_uval == 0xC1B1CC77
    pqspr_file.omega.commit()
    assert pqspr_file.omega.read_unsigned() == 0xC1B1CC77
    assert pqspr_file.omega._next_uval == None
    
def test_omega_mark_written(pqspr_file):
    pqspr_file._pending_writes.clear()
    assert not pqspr_file._pending_writes
    pqspr_file.omega.update()
    assert 3 in pqspr_file._pending_writes
    pqspr_file.commit()
    assert not pqspr_file._pending_writes
    
def test_psi_update1(pqspr_file):
    # test 1
    pqspr_file.omega.write_unsigned(0x55555555)
    pqspr_file.commit()
    
    assert pqspr_file.psi._uval == 0
    assert pqspr_file.psi._next_uval == None
    pqspr_file.psi.update()
    assert pqspr_file.psi._uval == 0
    pqspr_file.psi.commit()
    
    hex_value = hex(pqspr_file.psi.read_unsigned())
    print(hex_value)

    assert pqspr_file.psi.read_unsigned() == 0x5555555555555555555555555555555555555555555555555555555555555555
    
def test_psi_update2(pqspr_file):
    # test 2
    pqspr_file.omega.write_unsigned(0x01234567)
    pqspr_file.commit()
    
    assert pqspr_file.psi._uval == 0
    assert pqspr_file.psi._next_uval == None
    pqspr_file.psi.update()
    assert pqspr_file.psi._uval == 0
    pqspr_file.psi.commit()
    
    hex_value = hex(pqspr_file.psi.read_unsigned())
    print(hex_value)

    assert pqspr_file.psi.read_unsigned() == 0x01234567_01234567_01234567_01234567_01234567_01234567_01234567_01234567
    
def test_omega_mark_written(pqspr_file):
    pqspr_file._pending_writes.clear()
    assert not pqspr_file._pending_writes
    pqspr_file.psi.update()
    assert 4 in pqspr_file._pending_writes
    pqspr_file.commit()
    assert not pqspr_file._pending_writes
    
def test_m_update1(pqspr_file):
    # test 1
    pqspr_file.mode.write_unsigned(0)
    pqspr_file.m.write_unsigned(0xf)
    pqspr_file.commit()
    
    pqspr_file.m.update()
    assert pqspr_file.m.read_unsigned() == 0xf
    pqspr_file.m.commit()
    assert pqspr_file.m.read_unsigned() == 0x7
    
    pqspr_file.m.update()
    pqspr_file.m.commit()
    assert pqspr_file.m.read_unsigned() == 0x3
    
def test_m_update2(pqspr_file):
    # test 2
    pqspr_file.mode.write_unsigned(1)
    pqspr_file.m.write_unsigned(0x7)
    pqspr_file.commit()
    
    pqspr_file.m.update()
    assert pqspr_file.m.read_unsigned() == 0x7
    pqspr_file.m.commit()
    assert pqspr_file.m.read_unsigned() == 0xe
    
    pqspr_file.m.update()
    pqspr_file.m.commit()
    assert pqspr_file.m.read_unsigned() == 0x1c
    
def test_j2_update1(pqspr_file):
    # test 1
    pqspr_file.mode.write_unsigned(0)
    pqspr_file.j2.write_unsigned(0x7)
    pqspr_file.commit()
    
    pqspr_file.j2.update()
    assert pqspr_file.j2.read_unsigned() == 0x7
    pqspr_file.j2.commit()
    assert pqspr_file.j2.read_unsigned() == 0xe
    
    pqspr_file.j2.update()
    pqspr_file.j2.commit()
    assert pqspr_file.j2.read_unsigned() == 0x1c
    
def test_j2_update2(pqspr_file):
    # test 2
    pqspr_file.j2.write_unsigned(0x1c)
    pqspr_file.commit()
    assert pqspr_file.j2.read_unsigned() == 0x1c
    
    pqspr_file.mode.write_unsigned(1)
    pqspr_file.commit()
    
    pqspr_file.j2.update()
    assert pqspr_file.j2.read_unsigned() == 0x1c
    pqspr_file.j2.commit()
    assert pqspr_file.j2.read_unsigned() == 0xe
    
    pqspr_file.j2.update()
    pqspr_file.j2.commit()
    assert pqspr_file.j2.read_unsigned() == 0x7
    
def test_idx0(pqspr_file):
    pqspr_file.idx_0.write_unsigned(0x12)
    pqspr_file.commit()
    assert pqspr_file.idx_0.read_unsigned() == 0x12
    
    pqspr_file.idx_0.inc()
    pqspr_file.commit()
    assert pqspr_file.idx_0.read_unsigned() == 0x13
    
    assert not pqspr_file._pending_writes
    pqspr_file.idx_0.inc()
    assert 13 in pqspr_file._pending_writes
    pqspr_file.commit()
    assert not pqspr_file._pending_writes
    
    pqspr_file.j.write_unsigned(0x333)
    pqspr_file.commit()
    pqspr_file.idx_0.set()
    pqspr_file.commit()
    assert pqspr_file.idx_0.read_unsigned() == 0xcc
    
def test_idx1(pqspr_file):
    pqspr_file.idx_1.write_unsigned(0x12)
    pqspr_file.commit()
    assert pqspr_file.idx_1.read_unsigned() == 0x12
    
    pqspr_file.idx_1.inc()
    pqspr_file.commit()
    assert pqspr_file.idx_1.read_unsigned() == 0x13
    
    assert not pqspr_file._pending_writes
    pqspr_file.idx_1.inc()
    assert 14 in pqspr_file._pending_writes
    pqspr_file.commit()
    assert not pqspr_file._pending_writes
    
    pqspr_file.j.write_unsigned(0x333)
    pqspr_file.m.write_unsigned(0x11)
    pqspr_file.commit()
    pqspr_file.idx_1.set()
    pqspr_file.commit()
    assert pqspr_file.idx_1.read_unsigned() == 0xdd