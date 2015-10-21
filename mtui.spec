#
# spec file for package mtui
#
# Copyright (c) 2014 SUSE LINUX Products GmbH, Nuernberg, Germany.
#
# All modifications and additions to the file contributed by third parties
# remain the property of their copyright owners, unless otherwise agreed
# upon. The license for this file, and modifications and additions to the
# file, is the same license as for the pristine package itself (unless the
# license for the pristine package is not an Open Source License, in which
# case the license is the MIT License). An "Open Source License" is a
# license that conforms to the Open Source Definition (Version 1.9)
# published by the Open Source Initiative.

# Please submit bugfixes or comments via http://bugs.opensuse.org/
#


Name:           mtui
Version:        5.0.4
Release:        0
Summary:        Maintenance Test Update Installer
License:        SUSE-NonFree
Group:          Productivity/Other
Url:            http://qam.suse.de
Source0:        %{name}-%{version}.tar.gz
BuildRequires:  python-devel
BuildRequires:  python-setuptools
Requires:       osc
Requires:       python-paramiko
Requires:       python-setuptools
Requires:       python-xdg >= 0.21
Requires:       rpm-python
Recommends:     python-keyring
Recommends:     python-notify
Recommends:     xdg-utils
BuildRoot:      %{_tmppath}/%{name}-%{version}-build
%py_requires
%if 0%{?suse_version} && 0%{?suse_version} <= 1110
%{!?python_sitelib: %define python_sitelib %(python -c "from distutils.sysconfig import get_python_lib; print get_python_lib()")}
%else
BuildArch:      noarch
%endif

%description
SUSE QA Maintenance test update installer

%prep
%setup -q

%build
python setup.py build

%install
python setup.py install --prefix=%{_prefix} --root=%{buildroot}
mkdir -p %{buildroot}%{_sysconfdir}

cat <<EOF > %{buildroot}%{_sysconfdir}/mtui.cfg
[mtui]
datadir = %{_datadir}/mtui
[testopia]
interface = https://apibugzilla.novell.com/xmlrpc.cgi
[refhosts]
resolvers = https
https_uri = https://qam.suse.de/metadata/refhosts.xml
path = /usr/share/suse-qam-metadata/refhosts.xml
[url]
bugzilla = https://bugzilla.suse.com
EOF

mkdir -p %{buildroot}%{_datadir}/mtui
cp -a scripts %{buildroot}%{_datadir}/mtui/
cp -a helper %{buildroot}%{_datadir}/mtui/
install -Dm0755 term.gnome.sh term.kde.sh term.xterm.sh %{buildroot}%{_datadir}/mtui/

%files
%defattr(-,root,root,-)
%doc README.rst ChangeLog.rst Documentation/*
%{_bindir}/mtui*
%{_bindir}/refsearch.py
%{_datadir}/mtui/*
%dir %{_datadir}/mtui
%config %{_sysconfdir}/mtui.cfg
%{python_sitelib}/mtui*

%changelog
