"""Minimal read-only MIPS III disassembler used for the Boy model study."""

from __future__ import annotations

import argparse
import struct
from pathlib import Path

REG = ("zero", "at", "v0", "v1", "a0", "a1", "a2", "a3", "t0", "t1", "t2", "t3", "t4", "t5", "t6", "t7",
       "s0", "s1", "s2", "s3", "s4", "s5", "s6", "s7", "t8", "t9", "k0", "k1", "gp", "sp", "fp", "ra")


def signed(value: int, bits: int = 16) -> int:
    sign = 1 << (bits - 1)
    return (value ^ sign) - sign


def decode(word: int, pc: int) -> str:
    op, rs, rt, rd, sa, fn = word >> 26, (word >> 21) & 31, (word >> 16) & 31, (word >> 11) & 31, (word >> 6) & 31, word & 63
    imm, simm = word & 0xffff, signed(word & 0xffff)
    r = REG
    if word == 0: return "nop"
    if op == 0:
        names = {0:"sll",2:"srl",3:"sra",4:"sllv",6:"srlv",7:"srav",8:"jr",9:"jalr",12:"syscall",13:"break",16:"mfhi",17:"mthi",18:"mflo",19:"mtlo",24:"mult",25:"multu",26:"div",27:"divu",32:"add",33:"addu",34:"sub",35:"subu",36:"and",37:"or",38:"xor",39:"nor",42:"slt",43:"sltu"}
        n = names.get(fn, f"special_{fn:02x}")
        if fn in (0,2,3): return f"{n} ${r[rd]},${r[rt]},{sa}"
        if fn in (4,6,7): return f"{n} ${r[rd]},${r[rt]},${r[rs]}"
        if fn == 8: return f"jr ${r[rs]}"
        if fn == 9: return f"jalr ${r[rd]},${r[rs]}"
        if fn in (16,18): return f"{n} ${r[rd]}"
        if fn in (17,19): return f"{n} ${r[rs]}"
        if fn in (24,25,26,27): return f"{n} ${r[rs]},${r[rt]}"
        return f"{n} ${r[rd]},${r[rs]},${r[rt]}"
    if op in (2,3):
        target = ((pc + 4) & 0xf0000000) | ((word & 0x03ffffff) << 2)
        return f"{'jal' if op == 3 else 'j'} 0x{target:08X}"
    if op == 1:
        names={0:"bltz",1:"bgez",16:"bltzal",17:"bgezal"}; target=pc+4+(simm<<2)
        return f"{names.get(rt, 'regimm_'+str(rt))} ${r[rs]},0x{target:08X}"
    if op in (4,5):
        target=pc+4+(simm<<2); return f"{'beq' if op==4 else 'bne'} ${r[rs]},${r[rt]},0x{target:08X}"
    if op in (6,7):
        target=pc+4+(simm<<2); return f"{'blez' if op==6 else 'bgtz'} ${r[rs]},0x{target:08X}"
    if op in (8,9,10,11): return f"{('addi','addiu','slti','sltiu')[op-8]} ${r[rt]},${r[rs]},{simm}"
    if op in (12,13,14): return f"{('andi','ori','xori')[op-12]} ${r[rt]},${r[rs]},0x{imm:X}"
    if op == 15: return f"lui ${r[rt]},0x{imm:X}"
    if op == 16:
        fmt=(word>>21)&31
        if fmt==0:return f"mfc0 ${r[rt]},${rd}"
        if fmt==4:return f"mtc0 ${r[rt]},${rd}"
        return f"cop0 0x{word&0x3ffffff:X}"
    if op == 17:
        fmt=(word>>21)&31
        if fmt==0:return f"mfc1 ${r[rt]},$f{rd}"
        if fmt==2:return f"cfc1 ${r[rt]},$f{rd}"
        if fmt==4:return f"mtc1 ${r[rt]},$f{rd}"
        if fmt==6:return f"ctc1 ${r[rt]},$f{rd}"
        if fmt==8:
            target=pc+4+(simm<<2); return f"bc1{'t' if rt&1 else 'f'} 0x{target:08X}"
        formats={16:"s",17:"d",20:"w",21:"l"}; funcs={0:"add",1:"sub",2:"mul",3:"div",4:"sqrt",5:"abs",6:"mov",7:"neg",32:"cvt.s",33:"cvt.d",36:"cvt.w",37:"cvt.l",50:"c.eq",60:"c.lt",62:"c.le"}
        return f"{funcs.get(fn,'cop1_'+hex(fn))}.{formats.get(fmt,str(fmt))} $f{sa},$f{rd},$f{rt}"
    mem={32:"lb",33:"lh",34:"lwl",35:"lw",36:"lbu",37:"lhu",38:"lwr",40:"sb",41:"sh",42:"swl",43:"sw",46:"swr",48:"ll",49:"lwc1",53:"ldc1",56:"sc",57:"swc1",61:"sdc1"}
    if op in mem:
        reg = f"$f{rt}" if op in (49,53,57,61) else f"${r[rt]}"
        return f"{mem[op]} {reg},{simm}(${r[rs]})"
    return f".word 0x{word:08X}"


def main() -> None:
    p=argparse.ArgumentParser(); p.add_argument("rom",type=Path); p.add_argument("start",type=lambda s:int(s,0)); p.add_argument("end",type=lambda s:int(s,0)); a=p.parse_args()
    data=a.rom.read_bytes(); base_vram=0x80000400; base_rom=0x1000
    for pc in range(a.start,a.end,4):
        at=base_rom+(pc-base_vram); word=struct.unpack_from(">I",data,at)[0]
        print(f"{pc:08X}  {word:08X}  {decode(word,pc)}")


if __name__ == "__main__": main()
