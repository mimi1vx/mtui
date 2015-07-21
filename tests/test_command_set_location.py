# -*- coding: utf-8 -*-

from nose.tools import eq_
from nose.tools import ok_

from mtui.messages import LocationChangedMessage

from tests.prompt import make_cp

from .utils import ConfigFake

def test_happy():
    """
    Test config.location changes to new and proper info message is logged
    """
    c = ConfigFake()
    old = c.location
    new = "foolocation"
    ok_(old != new, "precondition check")

    cp = make_cp(config = c)
    cp.do_set_location(new)

    eq_(cp.log.infos, [LocationChangedMessage(old, new)])
    eq_(c.location, new)

def test_message():
    """
    Test both new and old shows up in the message.

    bsc#904222
    """
    old, new = "foo", "qux"
    m1 = str(LocationChangedMessage("", ""))
    ok_(old not in m1)
    ok_(new not in m1)

    m2 = str(LocationChangedMessage(old, new))
    ok_(old in m2)
    ok_(new in m2)
