#!/usr/bin/env python3

import subprocess
import sys
import shlex
import argparse

compressor_modes = ["null", "lzma", "xz", "gzip", "bzip2"]

interpreters = {
    "sh": "|sh",
    "python": "|python",
    "python2": "|python2",
    "python3": "|python3",
    "bin": ">a;chmod +x a;./a",
}

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('-i', '--input', help='Input file to compress')
    parser.add_argument('-o', '--output', help='Output file to compress')
    parser.add_argument('-p', '--interpreter', help='Interpreter to use ({})'.format(", ".join(interpreters)))
    args = parser.parse_args()

    if args.input is None:
        in_data = sys.stdin.buffer.read()
    else:
        in_data = open(args.input, "rb").read()

    out_data = best_compression(in_data, interpreter=interpreters.get(args.interpreter, args.interpreter))

    if args.output is None:
        print("No output file specified, dry run finished.")
        sys.exit(0)

    with open(args.output, "wb") as f:
        f.write(out_data)
        subprocess.check_call("chmod +x {}".format(shlex.quote(args.output)), shell=True)

def replace_with_octal(cd, char):
    o = bytes(oct(ord(char))[2:], encoding='latin1')
    fullo = b"0" * (3 - len(o)) + o
    for i in range(10):
        d = bytes(str(i), encoding='latin1')
        cd = cd.replace(char + d, b'\\' + fullo + d)
    cd = cd.replace(char, b'\\' + o)
    return cd

def best_compression(input_binary, *args, **kwargs):
    results = [compress(input_binary, mode, *args, **kwargs)
        for mode in compressor_modes]
    for mode, result in zip(compressor_modes, results):
        print("Method", mode, "gives size", len(result))
    best = min(zip(compressor_modes, results), key=lambda x: len(x[1]))
    print(best[0], "is the winner, with size", len(best[1]))
    return best[1]

def compress(input_binary, method="lzma9", interpreter="|sh"):
    # Map from common name to (compressor, decompressor) tuple
    if method == "null":
        return input_binary

    methods = {
        "lzma": ("xz -F lzma -cze9", "|unxz"),
        "xz": ("xz -F xz -cze9", "|unxz"),
        "gzip": ("gzip -9", "|zcat"),
        "bzip2": ("bzip2 -9", "|bzcat"),
    }
    (compressor, decompressor) = methods[method]

    proc = subprocess.Popen(compressor, shell=True, stdin=subprocess.PIPE, stdout=subprocess.PIPE)
    cd = proc.communicate(input_binary)[0]
    if proc.returncode != 0:
        raise ValueError("Process exited with returncode {}".format(proc.returncode))

    #lencd = len(cd)
    #print("Length of compressed data is", lencd)
    cd = cd.replace(b'\\', b'\\\\')
    cd = cd.replace(b'%', b'%%')
    cd = replace_with_octal(cd, b'\0')
    cd = replace_with_octal(cd, b"'")
    #lensecd = len(cd)
    #print("Length shell-escaped compressed data is", lensecd, "(ratio", lensecd / lencd, ")")

    return b"printf '" + cd + b"'" + bytes(decompressor, encoding='latin1') + bytes(interpreter, encoding='latin1')

if __name__ == "__main__":
    main()
