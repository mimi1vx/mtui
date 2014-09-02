#!/bin/bash

export LC_ALL=C

help () {
   cat <<EOF

usage: $0 -p <path-to-filelist> [id]

where id is either \$md5sum or (openSUSE|SUSE):Maintenance:\$issue:\$request

$0 compares initrd files to system files

EOF
}

ARGS=$(getopt -o p:r:h -- "$@")

if [ $? -gt 0 ]; then help; exit 1; fi

eval set -- "$ARGS"

while true; do
   case "$1" in
      -p) shift; plist="$1"; shift; ;;
      -r) shift; echo "INFO: option -r is not implemented"; shift; ;;
      -h) shift; help="set" ;;
      --) shift; break; ;;
   esac
done

id="$1"

if [ -n "$help" -o -z "$plist" ]; then
   help
   exit 0
fi

list=$(
    sed -n '/\.delta\.\(log\|info\|rpm\)/! { /\.rpm$/p; }' $plist | while read p
    do
       pn=${p%-[^-]*-[^-]*\.[^.]*\.rpm}
       echo ${pn##*/}
    done | sort -u | xargs
)

if [ ! -f "/boot/initrd" ]; then
    echo "no initrd found"
    exit 3
fi

dir=$(mktemp -d /tmp/$progname.XXXXXX)

cd $dir && gunzip < /boot/initrd | cpio -i --make-directories > /dev/null 2>&1 

# try to find files which might end up in /boot/initrd
for package in $list; do
    for file in $(rpm -ql $package | sort); do
        if [ -f ".$file" ]; then
            if [ "$(md5sum "$file" | awk '{ print $1 }')" != "$(md5sum ".$file" | awk '{ print $1 }')" ]; then
                echo $file
            fi
        fi
    done
done

rm -rf $dir
