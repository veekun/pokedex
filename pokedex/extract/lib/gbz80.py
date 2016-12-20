"""Stuff for dealing with the Game Boy's Z80-ish machine code.  Most notably,
can do pattern-matching against a chunk of assembly with missing values.
"""
from collections import OrderedDict
from collections import defaultdict
import re

import attr

# TODO: would be nice to understand "cp a, #foo" and similar for xor/or/and/etc
# TODO: would be AMAZING to understand labels when searching for code wow

# This table is courtesy of pokemon-reverse-engineering-tools:
# https://github.com/pret/pokemon-reverse-engineering-tools/blob/master/pokemontools/gbz80disasm.py
gbz80_bitops = dict(enumerate([
    "rlc b",       "rlc c",       "rlc d",       "rlc e",       "rlc h",       "rlc l",       "rlc [hl]",       "rlc a",       # $00 - $07
    "rrc b",       "rrc c",       "rrc d",       "rrc e",       "rrc h",       "rrc l",       "rrc [hl]",       "rrc a",       # $08 - $0f
    "rl b",        "rl c",        "rl d",        "rl e",        "rl h",        "rl l",        "rl [hl]",        "rl a",        # $10 - $17
    "rr b",        "rr c",        "rr d",        "rr e",        "rr h",        "rr l",        "rr [hl]",        "rr a",        # $18 - $1f
    "sla b",       "sla c",       "sla d",       "sla e",       "sla h",       "sla l",       "sla [hl]",       "sla a",       # $20 - $27
    "sra b",       "sra c",       "sra d",       "sra e",       "sra h",       "sra l",       "sra [hl]",       "sra a",       # $28 - $2f
    "swap b",      "swap c",      "swap d",      "swap e",      "swap h",      "swap l",      "swap [hl]",      "swap a",      # $30 - $37
    "srl b",       "srl c",       "srl d",       "srl e",       "srl h",       "srl l",       "srl [hl]",       "srl a",       # $38 - $3f
    "bit $00, b",  "bit $00, c",  "bit $00, d",  "bit $00, e",  "bit $00, h",  "bit $00, l",  "bit $00, [hl]",  "bit $00, a",  # $40 - $47
    "bit $01, b",  "bit $01, c",  "bit $01, d",  "bit $01, e",  "bit $01, h",  "bit $01, l",  "bit $01, [hl]",  "bit $01, a",  # $48 - $4f
    "bit $02, b",  "bit $02, c",  "bit $02, d",  "bit $02, e",  "bit $02, h",  "bit $02, l",  "bit $02, [hl]",  "bit $02, a",  # $50 - $57
    "bit $03, b",  "bit $03, c",  "bit $03, d",  "bit $03, e",  "bit $03, h",  "bit $03, l",  "bit $03, [hl]",  "bit $03, a",  # $58 - $5f
    "bit $04, b",  "bit $04, c",  "bit $04, d",  "bit $04, e",  "bit $04, h",  "bit $04, l",  "bit $04, [hl]",  "bit $04, a",  # $60 - $67
    "bit $05, b",  "bit $05, c",  "bit $05, d",  "bit $05, e",  "bit $05, h",  "bit $05, l",  "bit $05, [hl]",  "bit $05, a",  # $68 - $6f
    "bit $06, b",  "bit $06, c",  "bit $06, d",  "bit $06, e",  "bit $06, h",  "bit $06, l",  "bit $06, [hl]",  "bit $06, a",  # $70 - $77
    "bit $07, b",  "bit $07, c",  "bit $07, d",  "bit $07, e",  "bit $07, h",  "bit $07, l",  "bit $07, [hl]",  "bit $07, a",  # $78 - $7f
    "res $00, b",  "res $00, c",  "res $00, d",  "res $00, e",  "res $00, h",  "res $00, l",  "res $00, [hl]",  "res $00, a",  # $80 - $87
    "res $01, b",  "res $01, c",  "res $01, d",  "res $01, e",  "res $01, h",  "res $01, l",  "res $01, [hl]",  "res $01, a",  # $88 - $8f
    "res $02, b",  "res $02, c",  "res $02, d",  "res $02, e",  "res $02, h",  "res $02, l",  "res $02, [hl]",  "res $02, a",  # $90 - $97
    "res $03, b",  "res $03, c",  "res $03, d",  "res $03, e",  "res $03, h",  "res $03, l",  "res $03, [hl]",  "res $03, a",  # $98 - $9f
    "res $04, b",  "res $04, c",  "res $04, d",  "res $04, e",  "res $04, h",  "res $04, l",  "res $04, [hl]",  "res $04, a",  # $a0 - $a7
    "res $05, b",  "res $05, c",  "res $05, d",  "res $05, e",  "res $05, h",  "res $05, l",  "res $05, [hl]",  "res $05, a",  # $a8 - $af
    "res $06, b",  "res $06, c",  "res $06, d",  "res $06, e",  "res $06, h",  "res $06, l",  "res $06, [hl]",  "res $06, a",  # $b0 - $b7
    "res $07, b",  "res $07, c",  "res $07, d",  "res $07, e",  "res $07, h",  "res $07, l",  "res $07, [hl]",  "res $07, a",  # $b8 - $bf
    "set $00, b",  "set $00, c",  "set $00, d",  "set $00, e",  "set $00, h",  "set $00, l",  "set $00, [hl]",  "set $00, a",  # $c0 - $c7
    "set $01, b",  "set $01, c",  "set $01, d",  "set $01, e",  "set $01, h",  "set $01, l",  "set $01, [hl]",  "set $01, a",  # $c8 - $cf
    "set $02, b",  "set $02, c",  "set $02, d",  "set $02, e",  "set $02, h",  "set $02, l",  "set $02, [hl]",  "set $02, a",  # $d0 - $d7
    "set $03, b",  "set $03, c",  "set $03, d",  "set $03, e",  "set $03, h",  "set $03, l",  "set $03, [hl]",  "set $03, a",  # $d8 - $df
    "set $04, b",  "set $04, c",  "set $04, d",  "set $04, e",  "set $04, h",  "set $04, l",  "set $04, [hl]",  "set $04, a",  # $e0 - $e7
    "set $05, b",  "set $05, c",  "set $05, d",  "set $05, e",  "set $05, h",  "set $05, l",  "set $05, [hl]",  "set $05, a",  # $e8 - $ef
    "set $06, b",  "set $06, c",  "set $06, d",  "set $06, e",  "set $06, h",  "set $06, l",  "set $06, [hl]",  "set $06, a",  # $f0 - $f7
    "set $07, b",  "set $07, c",  "set $07, d",  "set $07, e",  "set $07, h",  "set $07, l",  "set $07, [hl]",  "set $07, a"   # $f8 - $ff
]))

# This instruction list was carefully scraped from:
# http://www.pastraiser.com/cpu/gameboy/gameboy_opcodes.html
gbz80_instructions = {
    0x00: 'nop',
    0x01: 'ld bc, #d16',
    0x02: 'ld [bc], a',
    0x03: 'inc bc',
    0x04: 'inc b',
    0x05: 'dec b',
    0x06: 'ld b, #d8',
    0x07: 'rlca',
    0x08: 'ld [#a16], sp',
    0x09: 'add hl, bc',
    0x0a: 'ld a, [bc]',
    0x0b: 'dec bc',
    0x0c: 'inc c',
    0x0d: 'dec c',
    0x0e: 'ld c, #d8',
    0x0f: 'rrca',

    0x10: 'stop',
    0x11: 'ld de, #d16',
    0x12: 'ld [de], a',
    0x13: 'inc de',
    0x14: 'inc d',
    0x15: 'dec d',
    0x16: 'ld d, #d8',
    0x17: 'rla',
    0x18: 'jr #r8',
    0x19: 'add hl, de',
    0x1a: 'ld a, [de]',
    0x1b: 'dec de',
    0x1c: 'inc e',
    0x1d: 'dec e',
    0x1e: 'ld e, #d8',
    0x1f: 'rra',

    0x20: 'jr nz, #r8',
    0x21: 'ld hl, #d16',
    0x22: 'ld [hl+], a',
    0x23: 'inc hl',
    0x24: 'inc h',
    0x25: 'dec h',
    0x26: 'ld h, #d8',
    0x27: 'daa',
    0x28: 'jr z, #r8',
    0x29: 'add hl, hl',
    0x2a: 'ld a, [hl+]',
    0x2b: 'dec hl',
    0x2c: 'inc l',
    0x2d: 'dec l',
    0x2e: 'ld l, #d8',
    0x2f: 'cpl',

    0x30: 'jr nc, #r8',
    0x31: 'ld sp, #d16',
    0x32: 'ld [hl-], a',
    0x33: 'inc sp',
    0x34: 'inc [hl]',
    0x35: 'dec [hl]',
    0x36: 'ld [hl], #d8',
    0x37: 'scf',
    0x38: 'jr c, #r8',
    0x39: 'add hl, sp',
    0x3a: 'ld a, [hl-]',
    0x3b: 'dec sp',
    0x3c: 'inc a',
    0x3d: 'dec a',
    0x3e: 'ld a, #d8',
    0x3f: 'ccf',

    0x40: 'ld b, b',
    0x41: 'ld b, c',
    0x42: 'ld b, d',
    0x43: 'ld b, e',
    0x44: 'ld b, h',
    0x45: 'ld b, l',
    0x46: 'ld b, [hl]',
    0x47: 'ld b, a',
    0x48: 'ld c, b',
    0x49: 'ld c, c',
    0x4a: 'ld c, d',
    0x4b: 'ld c, e',
    0x4c: 'ld c, h',
    0x4d: 'ld c, l',
    0x4e: 'ld c, [hl]',
    0x4f: 'ld c, a',

    0x50: 'ld d, b',
    0x51: 'ld d, c',
    0x52: 'ld d, d',
    0x53: 'ld d, e',
    0x54: 'ld d, h',
    0x55: 'ld d, l',
    0x56: 'ld d, [hl]',
    0x57: 'ld d, a',
    0x58: 'ld e, b',
    0x59: 'ld e, c',
    0x5a: 'ld e, d',
    0x5b: 'ld e, e',
    0x5c: 'ld e, h',
    0x5d: 'ld e, l',
    0x5e: 'ld e, [hl]',
    0x5f: 'ld e, a',

    0x60: 'ld h, b',
    0x61: 'ld h, c',
    0x62: 'ld h, d',
    0x63: 'ld h, e',
    0x64: 'ld h, h',
    0x65: 'ld h, l',
    0x66: 'ld h, [hl]',
    0x67: 'ld h, a',
    0x68: 'ld l, b',
    0x69: 'ld l, c',
    0x6a: 'ld l, d',
    0x6b: 'ld l, e',
    0x6c: 'ld l, h',
    0x6d: 'ld l, l',
    0x6e: 'ld l, [hl]',
    0x6f: 'ld l, a',

    0x70: 'ld [hl], b',
    0x71: 'ld [hl], c',
    0x72: 'ld [hl], d',
    0x73: 'ld [hl], e',
    0x74: 'ld [hl], h',
    0x75: 'ld [hl], l',
    0x76: 'halt',
    0x77: 'ld [hl], a',
    0x78: 'ld a, b',
    0x79: 'ld a, c',
    0x7a: 'ld a, d',
    0x7b: 'ld a, e',
    0x7c: 'ld a, h',
    0x7d: 'ld a, l',
    0x7e: 'ld a, [hl]',
    0x7f: 'ld a, a',

    # TODO understand these as both "add a, b" and "add a"
    0x80: 'add a, b',
    0x81: 'add a, c',
    0x82: 'add a, d',
    0x83: 'add a, e',
    0x84: 'add a, h',
    0x85: 'add a, l',
    0x86: 'add a, [hl]',
    0x87: 'add a, a',
    0x88: 'adc a, b',
    0x89: 'adc a, c',
    0x8a: 'adc a, d',
    0x8b: 'adc a, e',
    0x8c: 'adc a, h',
    0x8d: 'adc a, l',
    0x8e: 'adc a, [hl]',
    0x8f: 'adc a, a',

    0x90: 'sub b',
    0x91: 'sub c',
    0x92: 'sub d',
    0x93: 'sub e',
    0x94: 'sub h',
    0x95: 'sub l',
    0x96: 'sub [hl]',
    0x97: 'sub a',
    0x98: 'sbc a, b',
    0x99: 'sbc a, c',
    0x9a: 'sbc a, d',
    0x9b: 'sbc a, e',
    0x9c: 'sbc a, h',
    0x9d: 'sbc a, l',
    0x9e: 'sbc a, [hl]',
    0x9f: 'sbc a, a',

    0xa0: 'and b',
    0xa1: 'and c',
    0xa2: 'and d',
    0xa3: 'and e',
    0xa4: 'and h',
    0xa5: 'and l',
    0xa6: 'and [hl]',
    0xa7: 'and a',
    0xa8: 'xor b',
    0xa9: 'xor c',
    0xaa: 'xor d',
    0xab: 'xor e',
    0xac: 'xor h',
    0xad: 'xor l',
    0xae: 'xor [hl]',
    0xaf: 'xor a',

    0xb0: 'or b',
    0xb1: 'or c',
    0xb2: 'or d',
    0xb3: 'or e',
    0xb4: 'or h',
    0xb5: 'or l',
    0xb6: 'or [hl]',
    0xb7: 'or a',
    0xb8: 'cp b',
    0xb9: 'cp c',
    0xba: 'cp d',
    0xbb: 'cp e',
    0xbc: 'cp h',
    0xbd: 'cp l',
    0xbe: 'cp [hl]',
    0xbf: 'cp a',

    0xc0: 'ret nz',
    0xc1: 'pop bc',
    0xc2: 'jp nz, #a16',
    0xc3: 'jp #a16',
    0xc4: 'call nz, #a16',
    0xc5: 'push bc',
    0xc6: 'add a, #d8',
    0xc7: 'rst $00',
    0xc8: 'ret z',
    0xc9: 'ret',
    0xca: 'jp z, #a16',
    0xcb: gbz80_bitops,
    0xcc: 'call z, #a16',
    0xcd: 'call #a16',
    0xce: 'adc a, #d8',
    0xcf: 'rst $08',

    0xd0: 'ret nc',
    0xd1: 'pop de',
    0xd2: 'jp nc, #a16',
    # 0xd3
    0xd4: 'call nc, #a16',
    0xd5: 'push de',
    0xd6: 'sub #d8',
    0xd7: 'rst $10',
    0xd8: 'ret c',
    0xd9: 'reti',
    0xda: 'jp c, #a16',
    # 0xdb
    0xdc: 'call c, #a16',
    # 0xdd
    0xde: 'sbc a, #d8',
    0xdf: 'rst $18',

    0xe0: 'ldh [#a8], a',
    0xe1: 'pop hl',
    0xe2: 'ld [$ff00+c], a',  # XXX table claims 2 but this looks like 1 to me
    # 0xe3
    # 0xe4
    0xe5: 'push hl',
    0xe6: 'and #d8',
    0xe7: 'rst $20',
    0xe8: 'add sp, #r8',
    0xe9: 'jp [hl]',
    0xea: 'ld [#a16], a',
    # 0xeb
    # 0xec
    # 0xed
    0xee: 'xor #d8',
    0xef: 'rst $28',

    # TODO really want better support for this
    0xf0: 'ldh a, [#a8]',
    0xf1: 'pop af',
    0xf2: 'ld a, [$ff00+c]',  # XXX table says 1 but this looks like 1 to me
    0xf3: 'di',
    # 0xf4
    0xf5: 'push af',
    0xf6: 'or #d8',
    0xf7: 'rst $30',
    0xf8: 'ld hl, sp+#r8',
    0xf9: 'ld sp, hl',
    0xfa: 'ld a, [#a16]',
    0xfb: 'ei',
    # 0xfc
    # 0xfd
    0xfe: 'cp #d8',
    0xff: 'rst $38',
}


class Atom:
    is_constant = False
    is_input = False
    is_register = False

    def is_compatible_with(self, other):
        return self == other

    def render(self):
        raise NotImplementedError


@attr.s
class InputAtom(Atom):
    name = attr.ib()
    length = attr.ib()
    is_input = True

    def is_compatible_with(self, other):
        # Inputs are compatible with anything that's not a register
        # TODO does length matter?
        return isinstance(other, (InputAtom, ConstantAtom))

    def render(self, value=None):
        if value is None:
            return '#' + self.name
        else:
            return "${:0{width}x}".format(value, width=self.length * 2)


@attr.s
class RegisterAtom(Atom):
    name = attr.ib()
    is_register = True

    def render(self):
        return self.name


@attr.s
class ConstantAtom(Atom):
    value = attr.ib()
    is_constant = True

    def render(self):
        if self.value < 256:
            return "${:02x}".format(self.value)
        else:
            return "${:04x}".format(self.value)


class Instruction:
    def __init__(self, syntax, prefix, mnemonic, length, args, inputs):
        self.syntax = syntax
        self.prefix = prefix
        self.mnemonic = mnemonic
        self.length = length
        # list of (items_to_sum, is_pointer) tuples
        self.args = args
        self.inputs = inputs

    @staticmethod
    def partial_parse(syntax):
        mnemonic, *argstrs = re.split('[, ]+', syntax)
        args = []

        for argstr in argstrs:
            ptr = False
            if argstr.startswith('[') and argstr.endswith(']'):
                ptr = True
                argstr = argstr[1:-1]

            atoms = []
            for atomstr in re.split('[+](?=.)', argstr):
                if atomstr.startswith('#'):
                    atom = InputAtom(atomstr[1:], None)
                elif atomstr in (
                        'a', 'f', 'b', 'c', 'd', 'e', 'h', 'l',
                        'af', 'bc', 'de', 'hl', 'hl+', 'hl-',
                        'sp', 'pc', 'z', 'nz', 'c', 'nc',
                        ):
                    atom = RegisterAtom(atomstr)
                elif atomstr.startswith('$'):
                    atom = ConstantAtom(int(atomstr[1:], 16))
                elif atomstr.isdigit():
                    atom = ConstantAtom(int(atomstr))
                else:
                    raise SyntaxError(
                        "Unrecognized argument {!r} in instruction {!r}"
                        .format(atomstr, syntax))

                atoms.append(atom)

            args.append((atoms, ptr))

        return mnemonic, args

    @classmethod
    def parse(cls, syntax, prefix):
        mnemonic, args = cls.partial_parse(syntax)
        inputs = []

        length = len(prefix)
        for atoms, is_ptr in args:
            for atom in atoms:
                if not atom.is_input:
                    continue
                if atom.name in ('d16', 'a16'):
                    atom.length = 2
                elif atom.name in ('d8', 'a8', 'r8'):
                    atom.length = 1
                else:
                    raise SyntaxError(
                        "Unrecognized input name {}".format(atom.name))

                inputs.append(atom)
                length += atom.length

        self = cls(syntax, prefix, mnemonic, length, args, inputs)
        assert self(ignore_inputs=True) == syntax
        return self

    def __repr__(self):
        return "<{} 0x{}: {}>".format(
            type(self).__name__,
            self.prefix.hex(),
            self(ignore_inputs=True),
        )

    def __call__(self, *inputs, ignore_inputs=False):
        inputs = list(inputs)
        if not ignore_inputs:
            if len(inputs) != len(self.inputs):
                raise TypeError(
                    "{} needs {} inputs, got {}"
                    .format(self.syntax, len(self.inputs), len(inputs)))

        args = []
        for atoms, is_ptr in self.args:
            atomstrs = []
            for atom in atoms:
                if not ignore_inputs and atom.is_input:
                    atomstrs.append(atom.render(inputs.pop(0)))
                else:
                    atomstrs.append(atom.render())
            expr = '+'.join(atomstrs)
            if is_ptr:
                expr = '[' + expr + ']'
            args.append(expr)

        out = self.mnemonic
        if args:
            out = out + ' ' + ', '.join(args)
        return out

    def match_inputs(self, mnemonic, args):
        if self.mnemonic != mnemonic:
            return
        if len(self.args) != len(args):
            return

        # Compare args
        input_pairs = []
        for (atoms1, ptr1), (atoms2, ptr2) in zip(self.args, args):
            if ptr1 != ptr2:
                return
            if len(atoms1) != len(atoms2):
                return
            # TODO technically, A+B is the same as B+A, but the lists are het
            # so i can't sort
            # TODO also, constant folding could make A+B the same as C
            for atom1, atom2 in zip(atoms1, atoms2):
                if not atom1.is_compatible_with(atom2):
                    return
                if atom1.is_input:
                    input_pairs.append((atom1, atom2))

        return input_pairs


class InstructionSet:
    def __init__(self, instructions):
        self.instructions = {}
        self.mnemonics = defaultdict(set)
        self._load_instructions(instructions)

    def _load_instructions(self, instructions, *, prefix=b''):
        for n, syntax in instructions.items():
            byte = bytes([n])
            if isinstance(syntax, dict):
                # Nested args, for the bitops instruction
                self._load_instructions(syntax, prefix=byte)
            else:
                instr = Instruction.parse(syntax, prefix + byte)
                self.instructions[prefix + byte] = instr
                self.mnemonics[instr.mnemonic].add(instr)


gbz80 = InstructionSet(gbz80_instructions)

needle = """push bc
push hl
ld a, [#wd11e]
dec a
ld hl, #PokedexOrder
ld b, 0
ld c, a
add hl, bc
ld a, [hl]
ld [#wd11e], a
pop hl
pop bc
ret"""
"""
            \xc5        
            \xe5        
            \xfa (..)   
            \x3d        
            \x21 (..)   
            \x06 \x00   
            \x4f        
            \x09        
            \x7e        
            \xea \1     
            \xe1        
            \xc1        
            \xc9        
            """
haystack = b'\xc5\xe5\xfaXY\x3d\x21ZW\x06\x00\x4f\x09\x7e\xeaXY\xe1\xc1\xc9'

# ------------------------------------------------------------------------------
# Disassemble

def disassemble(haystack):
    i = 0
    while i < len(haystack):
        for l in range(2):
            prefix = haystack[i:i+l+1]
            if prefix in gbz80.instructions:
                instr = gbz80.instructions[prefix]
                break
        else:
            raise SyntaxError

        i += len(prefix)
        inputs = []
        for inp in instr.inputs:
            inputs.append(int.from_bytes(
                haystack[i:i + inp.length], byteorder='little'))
            i += inp.length

        print(instr(*inputs))


# ------------------------------------------------------------------------------
# Pattern match

def find_code(haystack, needle, **kwargs):
    # TODO error if something in kwargs isn't a pattern input?
    # TODO the return value here is goofy
    # TODO maybe use finditer and yield instead
    pattern_chunks = []
    input_table = OrderedDict()
    matched_instructions = []
    for instruction in needle.splitlines():
        instruction = re.sub(';.*', '', instruction).strip()
        if not instruction:
            continue
        mnemonic, args = Instruction.partial_parse(instruction)
        candidates = gbz80.mnemonics[mnemonic]
        for candidate in candidates:
            inputs = candidate.match_inputs(mnemonic, args)
            if inputs is not None:
                break
        else:
            raise SyntaxError(
                "Can't figure out what instruction corresponds to: "
                + instruction)

        instr = candidate
        pattern_chunks.append(re.escape(instr.prefix))
        pattern_atoms = []
        for instr_input, pattern_atom in inputs:
            pattern_atoms.append(pattern_atom)
            if pattern_atom.is_constant:
                pattern_chunks.append(re.escape(
                    pattern_atom.value.to_bytes(
                        instr_input.length, byteorder='little')))
            elif pattern_atom.name in input_table:
                pattern_chunks.append(input_table[pattern_atom.name])
            else:
                if pattern_atom.name in kwargs:
                    inner_pattern = re.escape(
                        kwargs[pattern_atom.name].to_bytes(
                            instr_input.length, byteorder='little'))
                else:
                    inner_pattern = b'.' * instr_input.length

                group_name = pattern_atom.name.encode('ascii')
                input_table[pattern_atom.name] = b'(?P=' + group_name + b')'
                pattern_chunks.append(
                    b'(?P<' + group_name + b'>' + inner_pattern + b')')
        matched_instructions.append((instr, pattern_atoms))

    pattern = b''.join(pattern_chunks)

    m = re.search(pattern, haystack, flags=re.DOTALL)
    if m:
        matched_inputs = {}
        for inp in input_table:
            matched_inputs[inp] = int.from_bytes(
                m.group(inp), byteorder='little')

        for instr, pattern_atoms in matched_instructions:
            inputs = []
            for atom in pattern_atoms:
                if atom.is_constant:
                    inputs.append(atom.value)
                else:
                    inputs.append(matched_inputs[atom.name])

        return m, matched_inputs
    else:
        return
