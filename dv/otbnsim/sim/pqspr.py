
from typing import Optional, List, Sequence
from .reg import Reg

from .trace import Trace

class TracePQSPR(Trace):
    def __init__(self, name: str, width: int, new_value: Optional[int]):
        self.name = name
        self.width = width
        self.new_value = new_value

    def trace(self) -> str:
        if self.new_value is not None:
            fmt_str = '{{}} = 0x{{:0{}x}}'.format(self.width // 4)
            return fmt_str.format(self.name, self.new_value)
        else:
            return '0x' + 'x' * (self.width // 4)

    def rtl_trace(self) -> str:
        return '> {}: {}'.format(self.name,
                                 Trace.hex_value(self.new_value, self.width))

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
        
class PQSPRegOmega(Reg):
    '''Class for omega
    Length is 256 bits'''
    def __init__(self, parent, idx, uval=0):
        super().__init__(parent, idx, width=256, uval=uval)
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
        
class PQSPRegPsi(Reg):
    '''Class for psi
    Length is 256 bits'''
    def __init__(self, parent, idx, uval=0):
        super().__init__(parent, idx, width=256, uval=uval)
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
        
class PQSPRegJ2(Reg):
    '''Class for j2 register
    Length is 32 bits'''
    def __init__(self, parent, idx, uval):
        super().__init__(parent, idx, width=32, uval=uval)
        self.parent = parent
        
    def update(self):
        m = self.read_unsigned()
        mode = self.parent.mode.read_unsigned()
        
        self._next_uval = ((m & 0x7f) >> 1) if mode else ((m & 0xff) << 1)
        self._mark_written()
        
class PQSPRegIncIdx(PQSPRegInc):
    def __init__(self, parent, idx, uval):
        super().__init__(parent, idx, uval=uval)
        self.parent = parent
    
    def read_register(self) -> int:
        return self._uval >> 3
    
    def read_word_idx(self) -> int:
        return self._uval & 0x7
        
class PQSPRegIncIdx0(PQSPRegIncIdx):
    '''Class for idx0 register
    length is 32 bit'''
    def __init__(self, parent, idx, uval):
        super().__init__(parent, idx, uval=uval)
        self.parent = parent
        
    def set(self):
        value = self.parent.j.read_unsigned() & 0xFF
        # bit reverse
        bit_reverse = int(f"{value:08b}"[::-1], 2)
        
        self._next_uval = bit_reverse
        self._mark_written()
        
class PQSPRegIncIdx1(PQSPRegIncIdx):
    '''Class for idx1 register
    length is 32 bit'''
    def __init__(self, parent, idx, uval):
        super().__init__(parent, idx, uval=uval)
        self.parent = parent
        
    def set(self):
        value = self.parent.j.read_unsigned() & 0xFF
        # bit reverse + m
        bit_reverse = int(f"{value:08b}"[::-1], 2)
        add = (bit_reverse + self.parent.m.read_unsigned()) & 0xff
        
        self._next_uval = add
        self._mark_written()

class PQSPRFile:
    '''Models the Post-Quantum Special Purpose Register File'''
    def __init__(self, name_pfx: str):
        self._name_pfx = name_pfx
        self._width = 256 # for tracing
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
        self.rc = Reg(self, 8, 256, 0)
        self.idx_rc = PQSPRegInc(self, 9, 0)
        # RAU
        self.m = PQSPRegM(self, 10, 0)
        self.j2 = PQSPRegJ2(self, 11, 0)
        self.j = PQSPRegInc(self, 12, 0)
        self.idx_0 = PQSPRegIncIdx0(self, 13, 0)
        self.idx_1 = PQSPRegIncIdx1(self, 14, 0)
        self.mode = Reg(self, 15, 32, 0)
        self.x = PQSPRegInc(self, 16, 0)
        self.y = PQSPRegInc(self, 17, 0)
        
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
            11: self.j2,
            12: self.j,
            13: self.idx_0,
            14: self.idx_1,
            15: self.mode,
            16: self.x,
            17: self.y
        }
        
    def mark_written(self, idx: int) -> None:
        '''Mark a register as having been written'''
        assert 0 <= len(self._by_idx)
        self._pending_writes.add(idx)
        
    def get_reg(self, idx: int) -> Reg:
        assert 0 <= idx < len(self._by_idx)
        return self._by_idx[idx]
        
    def changes(self) -> List[TracePQSPR]:
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