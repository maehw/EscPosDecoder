#!/usr/bin/python3
"""
Simple application using the EscPosDecoder ESC/POS binary decoder class in its
processing loop.
The application opens a TCP/IP port to listen for incoming data.
The incoming data is fed to the decoder.
After no more data has been received, the data is decoded as whole block.
The whole data is re-transmit to the real printer via TCP/IP.
Furthermore, the decoded text is encoded as JSON message and
(TODO) forwarded to a webserver for further processing.
"""
import sys
import socket
import json
import argparse
from esc_pos_decoder import EscPosDecoder


def forward_to_printer(printer_hostname="printer", printer_port=9001, raw_data=b""):
    completed = False
    try:
        # Create a TCP/IP socket
        tx_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        tx_sock.settimeout(3)
        print(f"Connecting to real printer on {printer_hostname}:{printer_port}")
        tx_sock.connect((printer_hostname, printer_port))
        # Send data
        print(f"Sending message '{raw_data}'")
        tx_sock.sendall(raw_data)
        completed = True
    except ConnectionRefusedError:
        print("Connection to printer refused")
        pass
    except socket.gaierror:
        print("Connection to printed failed")
        pass
    finally:
        print("Closing socket")
        tx_sock.close()
    return completed


def main(args):
    parser = argparse.ArgumentParser()

    parser.add_argument('-lp', '--listener-port', type=int, default=9100)

    parser.add_argument('-ph', '--printer-hostname', type=str, default="printer")

    parser.add_argument('-pp', '--printer-port', type=int, default=9100)

    parser.add_argument('-v', '--verbose', action='count', default=0)

    args = parser.parse_args()

    print(f"listener port:    {args.listener_port}")
    print(f"printer hostname: {args.printer_hostname}")
    print(f"printer port:     {args.printer_port}")

    # Create a TCP/IP socket
    rx_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

    server_hostname = "0.0.0.0"  # public interface ("localhost" would be limited to local interface)
    server_port = args.listener_port  # raw networking printing protocol

    # Bind the socket to the port
    print(f"Starting webserver on {server_hostname}:{server_port}")
    rx_sock.bind((server_hostname, server_port))

    # Listen for incoming connections
    rx_sock.listen(1)

    while True:
        # Wait for a TCP/IP connection
        print("Waiting for connection")
        connection, client_address = rx_sock.accept()
        tx_message = {
            "decoder_status": "unknown",
            "printer_status": "unknown",
            "receipt_content": {
                "lines": ""
            }
        }
        # Connection has been established
        try:
            print(f"Connection from {client_address[0]}:{client_address[1]}")
            decoder = EscPosDecoder(args.verbose)
            print(f"Decoder: {decoder}")
            raw_data = b""

            while True:
                raw_data_chunk = connection.recv(16)
                if raw_data_chunk:
                    # print(f"Received data: {raw_data_chunk}")
                    decoder.feed_bytes(raw_data_chunk)
                    raw_data = raw_data + raw_data_chunk
                else:
                    print(f"No more data from {client_address[0]}:{client_address[1]}")
                    break
            print("Out of decoding loop.")
            # terminate decoder/parser
            receipt_text = decoder.get_text()
            print("-"*48)
            print(receipt_text)
            print("-"*48)

            # forward data to the real printer and add status info
            ret = forward_to_printer(printer_hostname=args.printer_hostname,
                                     printer_port=args.printer_port,
                                     raw_data=raw_data)
            if ret:
                print("Sent to printer")
                tx_message["printer_status"] = "success"
            else:
                print("Failed to send to printer")
                tx_message["printer_status"] = "error"

            # parse the decoded receipt content further
            tx_message["receipt_content"]["lines"] = receipt_text.strip().splitlines()

            # TODO: send the JSON data to the webserver
            print(json.dumps(tx_message, indent=4))

        finally:
            # Clean up the connection
            connection.close()
            if decoder:
                print("Deleting decoder object")
                del decoder


if __name__ == '__main__':
    import sys
    main(sys.argv[1:])
