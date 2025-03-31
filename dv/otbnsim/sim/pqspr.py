
from typing import Optional, List, Sequence
from .reg import Reg

from .trace import Trace

class TracePQSPR(Trace):
    pass

class PQSPRegWide(Reg):
    '''Extends the Reg by byte addressing.
    Length is fixed to 256 bits'''
    def __init__(self, parent, idx, uval=0):
        super().__init__(parent, idx, width=256, uval=uval)
    
    def read_word_unsigned(self, word_idx: int) -> int:
        """Extracts the 32-bit word at the given index (0-7)"""
        assert 0 <= word_idx < 8, "Word index out of range (0-7)"
        return (self._uval >> (word_idx * 32)) & 0xFFFFFFFF
        
    def _set_word(self, word_idx: int, value: int) -> None:
        """Sets the 32-bit word at the given index (0-7) while preserving others."""
        assert 0 <= word_idx < 8, "Word index out of range (0-7)"
        assert 0 <= value < (1 << 32), "Value must be a 32-bit unsigned integer"

        # Initialize _next_uval from _uval if it's None
        # Necessary for multiple word writes in same cycle
        if self._next_uval is None:
            self._next_uval = self._uval  

        # Clear the specific word and set the new value
        mask = 0xFFFFFFFF << (word_idx * 32)
        self._next_uval = (self._next_uval & ~mask) | (value << (word_idx * 32))

        self._mark_written()
      
    def write_word_unsigned(self, uval: int, idx: int) -> None:
        """Writes a 32-bit word to a specific word index (0-7)"""
        self._set_word(idx, uval)

    @property
    def B0(self) -> int:
        return self.read_word_unsigned(0)

    @B0.setter
    def B0(self, value: int) -> None:
        self._set_word(0, value)

    @property
    def B1(self) -> int:
        return self.read_word_unsigned(1)

    @B1.setter
    def B1(self, value: int) -> None:
        self._set_word(1, value)

    @property
    def B2(self) -> int:
        return self.read_word_unsigned(2)

    @B2.setter
    def B2(self, value: int) -> None:
        self._set_word(2, value)

    @property
    def B3(self) -> int:
        return self.read_word_unsigned(3)

    @B3.setter
    def B3(self, value: int) -> None:
        self._set_word(3, value)

    @property
    def B4(self) -> int:
        return self.read_word_unsigned(4)

    @B4.setter
    def B4(self, value: int) -> None:
        self._set_word(4, value)

    @property
    def B5(self) -> int:
        return self.read_word_unsigned(5)

    @B5.setter
    def B5(self, value: int) -> None:
        self._set_word(5, value)

    @property
    def B6(self) -> int:
        return self.read_word_unsigned(6)

    @B6.setter
    def B6(self, value: int) -> None:
        self._set_word(6, value)

    @property
    def B7(self) -> int:
        return self.read_word_unsigned(7)

    @B7.setter
    def B7(self, value: int) -> None:
        self._set_word(7, value)


class PQSPRegInc(Reg):
    '''Class for idx registers.
    Length is fixed to 32 bits'''
    def __init__(self, parent, idx, uval):
        super().__init__(parent, idx, width=32, uval=uval)
        
    def inc(self):
        '''Currently allows inc up to 32bit value'''
        assert self._uval < (1 << self._width) - 1, "Value exceeds 32-bit range"
        self._next_uval = self._uval + 1
        self._mark_written()
        
class PQSPRegTwiddle(Reg):
    '''Class for twiddle
    Length is 32 bits'''
    def __init__(self, parent, idx, uval):
        super().__init__(parent, idx, width=32, uval=uval)
        self.parent = parent
        
    def set_as_psi(self):
        """Uets twiddle to the currently indexed psi word"""
        self._next_uval = self.parent.psi.read_word_unsigned(self.parent.idx_psi.read_unsigned())
        self._mark_written()
        
    def inv(self):
        """Inverts twiddle by calculating: twiddle = prime - twiddle.
        With single modulo reduction.
        Prime must always be greater than twiddle."""      
        self._next_uval = self.parent.q.read_unsigned() - self._uval
        self._mark_written()
        
    def update(self):
        """Updates twiddle by calculating: twiddle = omega * twiddle
        with the Montgomery Multiplication"""
        omega = self.parent.omega.read_word_unsigned(self.parent.idx_omega.read_unsigned()) 
        q = self.parent.q.read_unsigned() 
        q_inv = self.parent.q_dash.read_unsigned() 
        twiddle = self._uval
        
        # this is the systemverilog implementation
        p = twiddle * omega
        m = (p & 0xFFFFFFFF) * q_inv
        s = p + ((m & 0xFFFFFFFF) * q)
        t = (s >> 32) & 0xFFFFFFFF
        if t >= q:
            t -= q
            
        self._next_uval = t        
        self._mark_written()
        
class PQSPRegOmega(PQSPRegWide):
    '''Class for omega
    Length is 256 bits'''
    def __init__(self, parent, idx, uval):
        super().__init__(parent, idx, uval=uval)
        self.parent = parent
        
    def update(self):
        """Updates omega by calculating: omega = omega * omega
        for each byte with the Montgomery Multiplication"""
        omega = self._uval
        q = self.parent.q.read_unsigned() 
        q_inv = self.parent.q_dash.read_unsigned()

        # this is the systemverilog implementation
        p = omega * omega
        m = (p & 0xFFFFFFFF) * q_inv
        s = p + ((m & 0xFFFFFFFF) * q)
        t = (s >> 32) & 0xFFFFFFFF
        if t >= q:
            t -= q
            
        self._next_uval = t        
        self._mark_written()
        
class PQSPRegPsi(PQSPRegWide):
    '''Class for psi
    Length is 256 bits'''
    def __init__(self, parent, idx, uval):
        super().__init__(parent, idx, uval=uval)
        self.parent = parent
        
    def update(self):
        omega = self.parent.omega.read_word_unsigned(self.parent.idx_psi.read_unsigned())
        for byte in range(8):
            self.write_word_unsigned(omega, byte)
        self._mark_written()
            
class PQSPRegM(Reg):
    '''Class for m register
    Length is 32 bits'''
    def __init__(self, parent, idx, uval):
        super().__init__(parent, idx, width=32, uval=uval)
        self.parent = parent
        
    def update(self):
        m = self.read_unsigned()
        mode = self.parent.mode.read_unsigned()
        
        self._next_uval = ((m & 0x7f) << 1) if mode else ((m & 0xff) >> 1)
        self._mark_written()
        
class PQSPRegIncIdx(PQSPRegInc):
    '''Class for idx register
    length is 32 bit'''
    def __init__(self, parent, idx, uval):
        super().__init__(parent, idx, uval=uval)
        self.parent = parent
        self.id = idx
        
    def set(self):
        value = self.parent.j.read_unsigned() & 0xFF
        # bit reverse (+ m)
        bit_reverse = int(f"{value:08b}"[::-1], 2)
        add = (bit_reverse + self.parent.m.read_unsigned()) & 0xff
        # choose result depending on idx0 (self.id=12) or idx1 (self.id=13)
        self._next_uval = bit_reverse if self.id == 12 else add
        self._mark_written()

class PQSPRFile:
    '''Models the Post-Quantum Special Purpose Register File'''
    def __init__(self):
        self._pending_writes = set()
        # TRCU
        self.q = Reg(self, 0, 32, 0)
        self.q_dash = Reg(self, 1, 32, 0)
        self.twiddle = PQSPRegTwiddle(self, 2, 0)
        self.omega = PQSPRegOmega(self, 3, 0)
        self.psi = PQSPRegPsi(self, 4, 0)
        self.idx_omega = PQSPRegInc(self, 5, 0)
        self.idx_psi = PQSPRegInc(self, 6, 0)
        self.const = Reg(self, 7, 32, 0)
        self.rc = PQSPRegWide(self, 8, 0)
        self.idx_rc = PQSPRegInc(self, 9, 0)
        # RAU
        self.m = PQSPRegM(self, 10, 0)
        self.j = PQSPRegInc(self, 11, 0)
        self.idx_0 = PQSPRegIncIdx(self, 12, 0)
        self.idx_1 = PQSPRegIncIdx(self, 13, 0)
        self.mode = Reg(self, 14, 32, 0)
        self.x = PQSPRegInc(self, 15, 0)
        self.y = PQSPRegInc(self, 16, 0)
        
        # Store registers in a dict to iterate over them
        self._by_idx = {
            0: self.q,
            1: self.q_dash,
            2: self.twiddle,
            3: self.omega,
            4: self.psi,
            5: self.idx_omega,
            6: self.idx_psi,
            7: self.const,
            8: self.rc,
            9: self.idx_rc,
            10: self.m,
            11: self.j,
            12: self.idx_0,
            13: self.idx_1,
            14: self.mode,
            15: self.x,
            16: self.y
        }
        
    def mark_written(self, idx: int) -> None:
        '''Mark a register as having been written'''
        assert 0 <= len(self._by_idx)
        self._pending_writes.add(idx)
        
    def get_reg(self, idx: int) -> Reg:
        assert 0 <= idx < len(self._by_idx)
        return self._by_idx[idx]
        
    def changes(self) -> List[TracePQSPR]:
        # todo
        ret = []
        for idx in sorted(self._pending_writes):
            assert 0 <= idx < len(self._by_idx)
            next_val = self.get_reg(idx).read_next()
            ret.append(TracePQSPR('{}{:02}'.format(self._name_pfx, idx),
                                     self._width,
                                     next_val))
        return ret
    
    def commit(self) -> None:
        for idx in self._pending_writes:
            assert 0 <= len(self._by_idx)
            self._by_idx[idx].commit()
        self._pending_writes.clear()
        
    def abort(self) -> None:
        for idx in self._pending_writes:
            assert 0 <= idx < len(self._by_idx)
            self._by_idx[idx].abort()
        self._pending_writes.clear()
        
    def peek_unsigned_values(self) -> List[int]:
        '''Get a list of the (unsigned) values of the registers'''
        return [reg.read_unsigned(backdoor=True) for reg in self._by_idx]
    
    def wipe(self) -> None:
        for r in self._by_idx.values():
            r.write_invalid()