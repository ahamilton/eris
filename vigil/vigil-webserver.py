#!/usr/bin/env python3.6


import gzip
import http.server
import os
import pickle
import sys

import fill3
import termstr
import tools


def appearance_as_html(appearance):
    lines = []
    all_styles = set()
    for line in appearance:
        html, styles = termstr.TermStr(line).as_html()
        all_styles.update(styles)
        lines.append(html)
    return ("\n".join(style.as_html() for style in all_styles) +
            '\n<pre>' + "<br>".join(lines) + "</pre>")


def make_page(widget):
    body = appearance_as_html(fill3.Border(widget).appearance_min())
    return ("<html><body>%s</body></html>" % body).encode("utf-8")


class Webserver(http.server.BaseHTTPRequestHandler):

    def _set_headers(self):
        self.send_response(200)
        self.send_header("Content-type", "text/html")
        self.end_headers()

    def do_GET(self):
        self._set_headers()
        if self.path == "/":
            page = make_page(summary_column)
        elif "/" in self.path[1:]:
            row, column = [int(value) for value in self.path[1:].split("/")]
            page = make_page(summary_column[row][column].result)
        else:
            return
        self.wfile.write(page)

    def do_HEAD(self):
        self._set_headers()

    def do_POST(self):
        self._set_headers()
        self.wfile.write("posted".encode("utf-8"))


def run(server_class=http.server.HTTPServer, handler_class=Webserver, port=80):
    server_address = ("", port)
    httpd = server_class(server_address, handler_class)
    print("Starting httpd...")
    httpd.serve_forever()


if __name__ == "__main__":
    pickle_path = os.path.join(tools.CACHE_PATH, "summary.pickle")
    with gzip.open(pickle_path, "rb") as file_:
        screen = pickle.load(file_)
    summary_column = screen._summary._column
    run()
