#!/usr/bin/python3
import pycodestyle
import esc_pos_decoder


def separator():
    print("-"*80)


if __name__ == '__main__':
    # perform checks with pycodestyle
    files = ['test_local.py', 'test_remote.py', 'app.py', 'esc_pos_decoder.py']
    for file in files:
        fchecker = pycodestyle.Checker(file, show_source=True)
        num_errors = fchecker.check_all(expected=["E501", "E722"])
        print(f"Found {num_errors} errors (and warnings) in file '{file}'")
        separator()

    # dynamic tests of decoder using existing files from the ./resources folder
    # (need to download those resources first before running the tests)
    res_folder = "./resources/"
    file_list = [
                 "zebra-farmers-market.bin",
                 "receipt-with-logo.bin",
                 "bit-image.bin",
                 "character-encodings.bin",
                 "demo.bin",
                 "graphics.bin"
                 ]
    for filename in file_list:
        filename = res_folder + filename
        print(f"Parsing test file '{filename}'")
        decoder = esc_pos_decoder.EscPosDecoder()
        decoder.parse_file(filename)
        print(f"Number of decoding errors: {decoder.get_num_decoding_errors()}")
        text = decoder.get_text()
        print(f"Decoded text (snippet): '{text[:10]}'")
        separator()

    # dynamic tests of decoder using empty byte array
    print("Empty byte array")
    decoder = esc_pos_decoder.EscPosDecoder()
    decoder.feed_bytes(b"")
    print(f"Number of decoding errors: {decoder.get_num_decoding_errors()}")
    text = decoder.get_text()
    print(f"Decoded text (snippet): '{text[:10]}'")
    separator()

    # dynamic tests of decoder using invalid sequences
    print("Byte array with invalid sequences")
    decoder = esc_pos_decoder.EscPosDecoder()
    decoder.feed_bytes(b"Banana\x1b\x42Hello\x1b\x23 Wurl\x01\x02d")
    print(f"Number of decoding errors: {decoder.get_num_decoding_errors()}")
    text = decoder.get_text()
    print(f"Decoded text (snippet): '{text[:20]}'")
    separator()
