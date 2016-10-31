#!/bin/bash
# THIS FILE IS PART OF THE CYLC SUITE ENGINE.
# Copyright (C) 2008-2016 NIWA
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#-------------------------------------------------------------------------------
# Test suite shuts down with error on missing port file
. "$(dirname "$0")/test_header"
set_test_number 3
install_suite "${TEST_NAME_BASE}" "${TEST_NAME_BASE}"

OPT_SET=
if [[ "${TEST_NAME_BASE}" == *-globalcfg ]]; then
    create_test_globalrc "" "
[cylc]
    health check interval = PT10S"
    OPT_SET='-s GLOBALCFG=True'
fi

run_ok "${TEST_NAME_BASE}-validate" cylc validate ${OPT_SET} "${SUITE_NAME}"
# Suite run directory is now a symbolic link, so we can easily delete it.
RUND="$(cylc get-global-config --print-run-dir)"
REAL_SUITE_RUND="$(mktemp -d "${RUND}/${SUITE_NAME}XXXXXXXX")"
ln -s "$(basename "${REAL_SUITE_RUND}")" "${RUND}/${SUITE_NAME}"
suite_run_fail "${TEST_NAME_BASE}-run" \
    cylc run --no-detach ${OPT_SET} "${SUITE_NAME}"
LOGD="${REAL_SUITE_RUND}/log"
grep_ok "${RUND}/${SUITE_NAME}: suite run directory not found" \
    "${LOGD}/suite/log"

rm -fr "${REAL_SUITE_RUND}"
purge_suite "${SUITE_NAME}"
exit
