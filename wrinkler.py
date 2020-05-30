#!/usr/bin/env python3

import subprocess
import sys
import shlex
import argparse

compressor_modes = ["lzma", "xz", "gzip", "bzip2", "zstd"]
data_modes = ["printf", "tail"]

interpreters = {
    "sh": "|sh",
    "python": "|python",
    "python2": "|python2",
    "python3": "|python3",
    "bin":  ">a;/lib/ld*o ./a", # smol
    "bin2": ">a;chmod +x a;./a", # 1 bytes larger but probably more robust
}

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('-i', '--input', help='Input file to compress')
    parser.add_argument('-o', '--output', help='Output file to compress')
    parser.add_argument('-p', '--interpreter', default="sh", help='Interpreter to use ({})'.format(", ".join(interpreters)))
    parser.add_argument('--zip', dest='zip_filter', help='Compression mode to use ({})'.format(", ".join(compressor_modes)))
    parser.add_argument('--data', dest='data_filter', help='Data mode to use ({})'.format(", ".join(data_modes)))
    args = parser.parse_args()

    if args.input is None:
        in_data = sys.stdin.buffer.read()
    else:
        in_data = open(args.input, "rb").read()

    out_data = best_compression(in_data, interpreter=interpreters.get(args.interpreter, args.interpreter), zip_filter=args.zip_filter, data_filter=args.data_filter)

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

def best_compression(input_binary, *args, zip_filter=None, data_filter=None, **kwargs):
    modes = [("null", "null")] + [(zip_mode, data_mode) for zip_mode in compressor_modes for data_mode in data_modes]
    modes = [(zip_mode, data_mode) for (zip_mode, data_mode) in modes
             if (zip_filter is None or zip_mode == zip_filter) and (data_filter is None or data_mode == data_filter)]

    results = [compress(input_binary, *mode, *args, **kwargs)
        for mode in modes]
    for mode, result in zip(modes, results):
        print("Method", mode, "gives size", len(result))
    best = min(zip(modes, results), key=lambda x: len(x[1]))
    print(best[0], "is the winner, with size", len(best[1]))
    return best[1]

def compress(input_binary, zip_method="lzma9", data_method="printf", interpreter="|sh"):
    # Map from common name to (compressor, decompressor) tuple
    if zip_method == "null":
        return input_binary

    zip_methods = {
        "lzma": ("xz -F lzma -cze9", "|unxz"),
        "xz": ("xz -F xz -cze9", "|unxz"),
        "gzip": ("gzip -9", "|zcat"),
        "bzip2": ("bzip2 -9", "|bzcat"),
        "zstd": ("zstd -19", "|unzstd"),
    }
    (compressor, decompressor) = zip_methods[zip_method]

    proc = subprocess.Popen(compressor, shell=True, stdin=subprocess.PIPE, stdout=subprocess.PIPE)
    cd = proc.communicate(input_binary)[0]
    if proc.returncode != 0:
        raise ValueError("Process exited with returncode {}".format(proc.returncode))

    if data_method == "printf":
        cd = cd.replace(b'\\', b'\\\\')
        cd = cd.replace(b'%', b'%%')
        cd = replace_with_octal(cd, b'\0')
        cd = replace_with_octal(cd, b"'")
        return b"printf '" + cd + b"'" + bytes(decompressor, encoding='latin1') + bytes(interpreter, encoding='latin1')
    elif data_method == "tail":
        return b"tail +2 $0" + bytes(decompressor, encoding='latin1') + bytes(interpreter, encoding='latin1') + b";exit\n" + cd
    else:
        raise ValueError("Unknown data method")

if __name__ == "__main__":
    main()
