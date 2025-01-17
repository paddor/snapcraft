# -*- Mode:Python; indent-tabs-mode:nil; tab-width:4 -*-
#
# Copyright (C) 2021 Patrik Wenger <paddor@gmail.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License version 3 as
# published by the Free Software Foundation.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

"""The ruby plugin is useful for ruby based parts.
It uses ruby-install to install Ruby and can use bundler to install
dependencies from a `Gemfile` found in the sources.

Additionally, this plugin uses the following plugin-specific keywords:
    - ruby-version:
      (string)
      The version of ruby you want this snap to run. (e.g. '3.0' or '2.7.2')
    - ruby-flavor:
      (string)
      Other flavors of ruby supported by ruby-install (e.g. 'jruby', ...)
    - ruby-gems:
      (list)
      A list of gems to install.
    - ruby-use-bundler
      (boolean)
      Use bundler to install gems from a Gemfile (defaults 'false').
    - ruby-prefix:
      (string)
      Prefix directory for installation (defaults '/usr').
    - ruby-shared:
      (boolean)
      Build ruby as a shared library (defaults 'false').
    - ruby-use-jemalloc:
      (boolean)
      Build ruby with libjemalloc (defaults 'false').
    - ruby-configure-options:
      (array of strings)
      Additional configure options to use when configuring ruby.
"""

import os
import re
import logging

from typing import Any, Dict, List, Set
from snapcraft.plugins.v2 import PluginV2


class RubyPlugin(PluginV2):
    @classmethod
    def get_schema(cls) -> Dict[str, Any]:
        return {
            "$schema": "http://json-schema.org/draft-04/schema#",
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "ruby-flavor": {
                    "type": "string",
                    "default": "ruby",
                },
                "ruby-version": {
                    "type": "string",
                    "default": "3.0",
                    "pattern": r"^\d+\.\d+(\.\d+)?$",
                },
                "ruby-use-bundler": {
                    "type": "boolean",
                    "default": False,
                },
                "ruby-prefix": {
                    "type": "string",
                    "default": "/usr",
                },
                "ruby-use-jemalloc": {
                    "type": "boolean",
                    "default": False,
                },
                "ruby-shared": {
                    "type": "boolean",
                    "default": False,
                },
                "ruby-configure-options": {
                    "type": "array",
                    "items": {"type": "string"},
                    "default": [],
                },
                "ruby-gems": {
                    "type": "array",
                    "items": {"type": "string"},
                    "default": [],
                },
            },
        }

    def get_build_snaps(self) -> Set[str]:
        return set()

    def get_build_packages(self) -> Set[str]:
        packages = {"curl"}

        if self.options.ruby_use_jemalloc:
            packages.add("libjemalloc-dev")

        return packages

    def get_build_environment(self) -> Dict[str, str]:
        env = {
            "PATH": f"${{SNAPCRAFT_PART_INSTALL}}{self.options.ruby_prefix}/bin:${{PATH}}",
        }

        if self.options.ruby_shared:
            # for finding ruby.so when running `gem` or `bundle`
            env["LD_LIBRARY_PATH"] = f"${{SNAPCRAFT_PART_INSTALL}}{self.options.ruby_prefix}/lib${{LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}}"

        return env

    def _configure_opts(self) -> List[str]:
        configure_opts = [
            "--without-baseruby",
            "--enable-load-relative",
            "--disable-install-doc",
        ] + self.options.ruby_configure_options

        if self.options.ruby_shared:
            configure_opts.append("--enable-shared")
        if self.options.ruby_use_jemalloc:
            configure_opts.append("--with-jemalloc")

        return configure_opts

    def get_build_commands(self) -> List[str]:
        # NOTE: To update ruby-install version, go to https://github.com/postmodern/ruby-install/tags
        ruby_install_version = '0.8.5'

        # NOTE: To update SHA256 checksum, run the following command (with updated version) and copy the output (one line) here:
        #   curl -L https://github.com/postmodern/ruby-install/archive/refs/tags/v0.8.5.tar.gz -o ruby-install.tar.gz && sha256sum --tag ruby-install.tar.gz
        ruby_install_checksum = 'SHA256 (ruby-install.tar.gz) = 793fcf44dce375c6c191003c3bfd22ebc85fa296d751808ab315872f5ee0179b'

        configure_opts = ' '.join(self._configure_opts())
        commands = []

        # NOTE: Download and verify ruby-install and use it to download, compile, and install Ruby
        commands.append(f"curl -L --proto '=https' --tlsv1.2 https://github.com/postmodern/ruby-install/archive/refs/tags/v{ruby_install_version}.tar.gz -o ruby-install.tar.gz")
        commands.append("echo 'Checksum of downloaded file:'")
        commands.append("sha256sum --tag ruby-install.tar.gz")
        commands.append("echo 'Checksum is correct if it matches:'")
        commands.append(f"echo '{ruby_install_checksum}'")
        commands.append(f"echo '{ruby_install_checksum}' | sha256sum --check --strict")
        commands.append("tar xfz ruby-install.tar.gz")
        commands.append(f"ruby-install-{ruby_install_version}/bin/ruby-install --src-dir ${{SNAPCRAFT_PART_SRC}} --install-dir ${{SNAPCRAFT_PART_INSTALL}}{self.options.ruby_prefix} --package-manager apt --jobs=${{SNAPCRAFT_PARALLEL_BUILD_COUNT}} {self.options.ruby_flavor}-{self.options.ruby_version} -- {configure_opts}")

        # NOTE: Update bundler and avoid conflicts/prompts about replacing bundler
        #       executables by removing them first.
        commands.append(f"rm -f ${{SNAPCRAFT_PART_INSTALL}}{self.options.ruby_prefix}/bin/{{bundle,bundler}}")
        commands.append("gem install --env-shebang --no-document bundler")

        if self.options.ruby_use_bundler:
            commands.append("bundle")

        if self.options.ruby_gems:
            commands.append("gem install --env-shebang --no-document {}".format(' '.join(self.options.ruby_gems)))

        return commands
