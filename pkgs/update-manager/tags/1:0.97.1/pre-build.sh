#!/bin/sh

# update demotions
#(cd utils && ./demotions.py intrepid jaunty > demotions.cfg)
#(cd utils && ./update_mirrors.py ../DistUpgrade/mirrors.cfg)

# run the test-suit
#echo "Running integrated tests"
#(cd tests && for test in *.py; do python $$test; done)

# update version
DEBVER=$(LC_ALL=C dpkg-parsechangelog |sed -n -e '/^Version:/s/^Version: //p' | sed s/.*://)
echo "VERSION='$DEBVER'" > DistUpgrade/DistUpgradeVersion.py

