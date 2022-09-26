#!/usr/bin/python3
"""
Usage examples:

    Decode binary ESC/POS from a file:
        from esc_pos_decoder import EscPosDecoder
        decoder = EscPosDecoder()
        decoder.parse_file("./resources/demo.bin")
        text = decoder.get_text()
        print(text)

    Decode binary ESC/POS from a byte stream:
        from esc_pos_decoder import EscPosDecoder
        decoder = EscPosDecoder()
        decoder.feed_bytes(b"Hello ")
        decoder.feed_bytes(b"world")
        decoder.feed_bytes(b"\n")
        text = decoder.get_text()
        print(text)
"""
from sys import byteorder
from enum import Enum


class EscPosDecoder:

    """ESC/POS binary decoder

    Example:
    >>> 1 == 1
    """

    # define constants
    ESC = b"\x1B"
    GS = b"\x1D"
    # the list of printable characters also contains cariage return and newline characters
    PRINTABLES = b'0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUV'\
        b'WXYZ!#$%&\'()*+,-./:;<=>?@[\\]^_`{|}~ "#$%&\'()+,-./:;<=>?@[\\]^_`'\
        b'{|}~ \t\n\r\x0b\x0c'

    class EscPosDecoderMode(Enum):
        """Enum of decoder modes
        """
        FILL_DATA_BUF = 1
        FILL_CMD_BUF = 2
        FILL_CMD_ARG_BUF = 3

    def __init__(self, verbose=0):
        self.verbose = verbose
        self.num_decoding_errors = 0

        # command decoding tree, one nesting level per command byte;
        # maps command byte arrays to calleables which process the command
        self.decoder_tree = {
            EscPosDecoder.ESC: {                     # 0x1B
                b"!": self._select_print_mode,         # 0x21
                b"%": self._select_userdef_charset,    # 0x25
                b"-": self._set_underline,             # 0x2D
                b"M": self._set_font,                  # 0x32
                b"@": self._initialize_printer,        # 0x40
                b"E": self._set_emphasis_mode,         # 0x45
                b"J": self._feed_forward_units,        # 0x4A
                b"V": self._cut,                       # 0x56
                b"a": self._select_justification,      # 0x61
                b"d": self._feed_forward_lines,        # 0x64
                b"p": self._pulse,                     # 0x70
                b"{": self._upside_down                # 0x7B
            },
            EscPosDecoder.GS: {                      # 0x1D
                b"!": self._set_character_size,        # 0x21
                b"(": {                                # 0x28
                    b"L": self._process_graphics_data  # 0x4C
                    # number of args depends on <fn>; could be listed here
                },
                b"L": self._set_left_margin,           # 0x4C
                b"V": self._cut_paper,                 # 0x56
                b"W": self._set_print_area_width,      # 0x57
                b"h": self._set_barcode_height         # 0x68
            }
        }

        self._reset()

    def _reset(self):
        # set initial decoder mode
        self.decoder_mode = EscPosDecoder.EscPosDecoderMode.FILL_DATA_BUF

        # number of characters in a row
        self.printout_width = 48

        # start with empty buffers and initializing counters
        self.cmd_buf = []
        self.cmd_arg_buf = []
        self.data_buf = []
        self.cmd_expected_nargs = 0
        self.num_parsed_bytes = 0
        self.out_buf = []

    def log_debug(self, msg, prefix=True):
        if self.verbose > 1:
            if prefix:
                print(f"[DEBUG] ", end="")
            print(msg)

    def log_info(self, msg, prefix=True):
        if self.verbose > 0:
            if prefix:
                print(f"[INFO] ", end="")
            print(msg)

    def log_warn(self, msg, prefix=True):
        if self.verbose > 0:
            if prefix:
                print(f"[WARN] ", end="")
            print(msg)

    # decorators
    def decoder_method(func):
        def decoder_method_wrapper(self, *args, **kwargs):
            if self.verbose > 0:
                self.log_debug(f"Calling decoder method '{func.__qualname__}'")
            return func(self, *args, **kwargs)
        return decoder_method_wrapper

    @decoder_method
    def parse_file(self, filename):
        """Parse a whole ECS/POS binary file
        """
        if type(filename) != str:
            raise TypeError("Expected filename as a string")

        self.log_info(f"Parsing file '{filename}'")
        f = open(filename, "rb")
        try:
            b = f.read(1)
            while b:
                self._feed_byte(b)
                b = f.read(1)
        finally:
            f.close()
        self.log_info(f"{self.printout_width*'-'}", False)
        self.log_info("Finished parsing file.")

    @decoder_method
    def get_text(self):
        # terminate feed (kind of flushig the buffers)
        self._terminate_feed()
        # self.log_debug(f"Contents of out buf: {self.out_buf}, type:{type(self.out_buf)}")
        if type(self.out_buf) is not list:
            raise TypeError("Expected output buffer to be a list")
        # join list of bytes
        self.out_buf = b''.join(self.out_buf)
        if type(self.out_buf) is not bytes:
            raise TypeError("Expected output buffer to be bytes")
        # self.log_debug(f"Contents of out buf: {self.out_buf}, type:{type(self.out_buf)}")

        self.log_info(f"Number of decoding errors: {self.num_decoding_errors}")
        self.log_info(f"Output:\n{self.printout_width*'-'}")
        text = self.out_buf.decode('UTF-8')

        self._reset()

        return text

    def get_num_decoding_errors(self):
        return self.num_decoding_errors

    def _initialize_printer(self):
        """Clears the data in the print buffer and resets the printer modes to
        the modes that were in effect when the power was turned on.
        """
        self.log_info("Initialize printer")
        pass

    def _set_print_area_width(self, nL, nH):
        """Set print area width
        """
        pa_width = int(nL[0]) + int(nH[0]*256)
        self.log_info(f"Set print area width: {pa_width}")

    def _set_left_margin(self, nL, nH):
        """Set left margin
        """
        margin = int(nL[0]) + int(nH[0]*256)
        self.log_info(f"Set left margin: {margin}")

    def _select_justification(self, n):
        """Select justification mode
        """
        n = int(n[0])
        if n == 0 or n == 48:
            self.log_info("Justification: left")
        elif n == 1 or n == 49:
            self.log_info("Justification: center")
        elif n == 2 or n == 50:
            self.log_info("Justification: right")
        else:
            self.log_info("Justification: unknown")
            raise ValueError

    def _select_print_mode(self, print_mode):
        """Select print mode
        """
        print_mode = int(print_mode[0])
        # inspect every bit
        if print_mode & 1:
            self.log_info("Print mode: font B")
        else:
            self.log_info("Print mode: font A")
        # 2? 4?
        if print_mode & 8:
            self.log_info("Print mode: emphasized")
        if print_mode & 16:
            self.log_info("Print mode: double height")
        if print_mode & 32:
            self.log_info("Print mode: double width")
        # 64 ?
        if print_mode & 128:
            self.log_info("Print mode: underline")

    def _cut(self, cut_mode):
        """Cut
        65: partial, 66: full
        """
        cut_mode = int(cut_mode[0])
        self.log_info(f"Cut mode: {cut_mode}")
        pass

    def _cut_paper(self, cut_mode):
        """Select cut mode and cut paper
        """
        cut_mode = int(cut_mode[0])
        self.log_info(f"Cut with cut mode: {cut_mode}/0x{cut_mode:02X} (depending on printer)")

    def _set_barcode_height(self, height):
        """Set barcode height
        """
        height = int(height[0])
        self.log_info(f"Barcode height: {height}")

    def _select_userdef_charset(self, n):
        n = int(n[0])
        if n & 1:
            self.log_info("User-defined character set is selected")
        else:
            self.log_info("User-defined character set is canceled")

    def _set_emphasis_mode(self, onoff):
        """Set emphasis mode
        1: enable, 0: disable
        """
        onoff = int(onoff[0])
        if onoff == 1:
            self.log_info("Emphasis enabled")
        else:
            self.log_info("Emphasis disabled")

    def _upside_down(self, onoff):
        onoff = int(onoff[0])
        if onoff & 1:
            self.log_info("Upside-down print mode turned on")
        else:
            self.log_info("Upside-down print mode turned off")

    def _set_underline(self, u):
        """Set underline

        0: no underline
        1: underline
        2: heavy underline
        """
        u = int(u[0])
        if u == 1:
            self.log_info("Underline")
        elif u == 2:
            self.log_info("Heavy underline")
        else:
            self.log_info("No underline")

    def _set_character_size(self, size):
        """Set character size
        - three LSBit of high nibble for width
        - three LSBit of low nibble for height
        """
        size = int(size[0])
        width = ((size & 0x70) >> 4) + 1
        height = (size & 0x07) + 1
        self.log_info(f"width: {width}, height: {height}")

    def _set_font(self, font):
        """Set font
        """
        pass

    def _feed_forward_lines(self, num_lines):
        """Feed forward for N lines
        """
        num_lines = int(num_lines[0])
        self.log_info(f"Feed forward for {num_lines} lines")
        self.out_buf.append(b"\n"*num_lines)

    def _feed_forward_units(self, num_units):
        """Feed forward for N lines
        """
        num_units = int(num_units[0])
        self.log_info(f"Feed forward for {num_units} units")
        self.out_buf.append(b"\n"*num_units)  # assume units are lines

    def _process_graphics_data(self, pl, ph, m, fn):
        """Process graphics buffer
        """
        # TODO/FIXME: separate by fn (switch/case), or better already do this
        # in the dict!
        # might get out of sync if command is not specified,
        # or needs to be reversed!
        pass

    def _pulse(self, m, t1, t2):
        """Pulse
        """
        m = int(m[0])
        t1 = int(t1[0])
        t2 = int(t2[0])
        self.log_info(f"Pulse (m={m}, t1={t1}, t2={t2})")
        pass

    @decoder_method
    def _data_buf_to_output(self):
        if self.data_buf:
            # sanity check for the contents of the data buffer (should be
            # printable, otherwise discard it); make visible for debugging
            # should makes the decoder robust against unknown or misintepreted
            # commands
            data_buf = b''.join(self.data_buf)
            has_non_printables = False
            for character in data_buf:
                has_non_printables = has_non_printables or \
                    (character not in EscPosDecoder.PRINTABLES)
            if not has_non_printables:
                self.out_buf.append(data_buf)
            else:
                self.log_debug(f"Non-printable data buffer: {data_buf}")
            self.data_buf = []

    @decoder_method
    def _terminate_feed(self):
        """Check remaining buffers
        """
        if self.decoder_mode == EscPosDecoder.EscPosDecoderMode.FILL_DATA_BUF:
            self.log_debug(f"Remaining data in data buffer: {self.data_buf}")
            self._data_buf_to_output()
        elif self.decoder_mode == EscPosDecoder.EscPosDecoderMode.FILL_CMD_BUF:
            self.log_debug(f"Remaining data in command buffer: {self.cmd_buf}"
                           f" (unexpected if has content or in this mode)")
        elif self.decoder_mode == EscPosDecoder.EscPosDecoderMode.FILL_CMD_ARG_BUF:
            self.log_debug(f"Remaining data in command arguments buffer: {self.cmd_arg_buf}"
                           f" (unexpected if has content or in this mode)")

    def printer_method_args_wrapper(self, func, args):
        self.log_info(f"Calling printer method '{func.__qualname__}' with args={self.cmd_arg_buf}")
        try:
            func(*args)
        except:  # TODO/FIXME: catch only specific exceptions
            # fail silently and only output a warning (productive mode)
            self.log_warn(f"Printer method '{func.__qualname__}' failed to execute.")
        self.cmd_buf = []
        self.cmd_arg_buf = []
        self.cmd_expected_nargs = 0
        self.decoder_mode = EscPosDecoder.EscPosDecoderMode.FILL_DATA_BUF

    # @decoder_method (uncomment for detailed debugging)
    def feed_bytes(self, bytes):
        """Feed in bytes and perform on-the-fly decoding
        """
        for b in bytes:
            b = b.to_bytes(1, byteorder)  # decoder need a bytes-like object, not ints
            self._feed_byte(b)

    # @decoder_method (uncomment for detailed debugging)
    def _feed_byte(self, b):
        """Parse a single byte dependent on current decoder mode.
        Note: This may change the decoder mode.
        """

        if self.decoder_mode == EscPosDecoder.EscPosDecoderMode.FILL_DATA_BUF:
            # fill data buffer (print payload) until start of a command is found
            if b in list(self.decoder_tree.keys()):
                # is the character a valid start of a command?
                # do not append to data but command buffer but terminate the
                # current data buffer, i.e. add it to output and then empty it
                self._data_buf_to_output()
                self.cmd_buf = [b]
                self.cmd_arg_buf = []
                self.cmd_expected_nargs = 0
                # switch mode
                self.decoder_mode = EscPosDecoder.EscPosDecoderMode.FILL_CMD_BUF
            else:
                # append data byte and stay in data collection mode
                self.data_buf.append(b)
        elif self.decoder_mode == EscPosDecoder.EscPosDecoderMode.FILL_CMD_BUF:
            # continue filling the command buffer (this is not the first byte!)
            # until a valid command has is decoded
            self.cmd_buf.append(b)
            # process the current command buffer;
            # inside this method the decoder_mode may switch to
            # EscPosDecoder.EscPosDecoderMode.FILL_CMD_ARG_BUF
            self._process_command_buffer()
        elif self.decoder_mode == EscPosDecoder.EscPosDecoderMode.FILL_CMD_ARG_BUF:
            # fill command buffer until the number of required arguments has been found
            self.cmd_arg_buf.append(b)
            # is the current number of collected argument bytes sufficient?
            # if so, call it with its arguments
            if len(self.cmd_arg_buf) == self.cmd_expected_nargs:
                printer_method = self._find_printer_method()
                self.printer_method_args_wrapper(printer_method, self.cmd_arg_buf)

    @decoder_method
    def _find_printer_method(self):
        search = self.decoder_tree  # copy the dict to be searched as it is modified during the process
        search_depth = 0
        try:
            for key in self.cmd_buf:
                search = search[key]
                search_depth = search_depth + 1
            return search
        # except (TypeError, KeyError):
        except KeyError:
            self.num_decoding_errors += 1
            self.log_warn(f"Unable to find command; cmd_buf={self.cmd_buf}.")
            self.cmd_arg_buf = []  # reset command arguments buffer
            self.cmd_buf = []  # also reset the command buffer
            self.decoder_mode = EscPosDecoder.EscPosDecoderMode.FILL_DATA_BUF
            self.log_debug(f"Search failed at search depth of {search_depth}!")
            return None

    @decoder_method
    def _process_command_buffer(self):
        """Parse current command buffer and
        - execute callable immediately when command is found which has no arguments,
        - start collecting command arguments when command is found that has arguments.
        """
        printer_method = self._find_printer_method()
        if callable(printer_method):
            nargs = printer_method.__code__.co_argcount - 1  # subtract one for 'self'

            self.cmd_arg_buf = []  # reset command arguments buffer
            if nargs == 0:
                self.log_info(f"Calling printer method '{printer_method.__qualname__}' without arguments")
                printer_method()  # this is the immediate call of the printer command method
                self.cmd_buf = []
                self.cmd_arg_buf = []
                self.cmd_expected_nargs = 0
                self.decoder_mode = EscPosDecoder.EscPosDecoderMode.FILL_DATA_BUF
            else:
                self.log_debug(f"Start collecting arguments for printer method '{printer_method.__qualname__}'")
                self.cmd_expected_nargs = nargs
                self.decoder_mode = EscPosDecoder.EscPosDecoderMode.FILL_CMD_ARG_BUF
