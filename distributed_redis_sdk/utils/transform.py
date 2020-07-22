# -*- coding: utf-8 -*-
"""
(C) Rgc <2020956572@qq.com>
All rights reserved
create time '2020/7/22 14:31'

Usage:

"""

import base64
import inspect
import pickle
import string
import uuid


def str2byte(_str):
    """
    str to bytes
    :param _str:
    :return:
    """
    return bytes(_str, encoding='utf8')


def byte2str(_bytes):
    """
    bytes to str
    :param _bytes:
    :return:
    """
    return str(_bytes, encoding="utf-8")


def normalize_timeout(timeout, default_timeout):
    """
    过滤缓存的过期时间
    :param timeout:
    :param default_timeout: 默认超时时间
    :return:
    """
    if timeout is None:
        timeout = default_timeout
    if timeout <= 0:
        timeout = -1
    return timeout


def dump_object(value):
    """Dumps an object into a string for redis.  By default it serializes
    integers as regular string and pickle dumps everything else.
    """
    t = type(value)
    if t == int:
        return str(value).encode("ascii")
    return b"!" + pickle.dumps(value)


def load_object(value):
    """The reversal of :meth:`dump_object`.  This might be called with
    None.
    """
    if value is None:
        return None
    if value.startswith(b"!"):
        try:
            return pickle.loads(value[1:])
        except pickle.PickleError:
            return None
    try:
        return int(value)
    except ValueError:
        # before 0.8 we did not have serialization.  Still support that.
        return value


def iteritems_wrapper(mappingorseq):
    """Wrapper for efficient iteration over mappings represented by dicts
    or sequences::

        >>> for k, v in iteritems_wrapper((i, i*i) for i in xrange(5)):
        ...    assert k*k == v

        >>> for k, v in iteritems_wrapper(dict((i, i*i) for i in xrange(5))):
        ...    assert k*k == v

    """
    if hasattr(mappingorseq, "items"):
        return mappingorseq.items()
    return mappingorseq


def memoize_make_version_hash():
    return base64.b64encode(uuid.uuid4().bytes)[:6].decode("utf-8")


def memvname(funcname):
    return funcname + "_memver"


def get_id(obj):
    return getattr(obj, "__caching_id__", repr)(obj)


def get_arg_names(f):
    """Return arguments of function

    :param f:
    :return: String list of arguments
    """
    sig = inspect.signature(f)
    return [
        parameter.name
        for parameter in sig.parameters.values()
        if parameter.kind == parameter.POSITIONAL_OR_KEYWORD
    ]


def wants_args(f):
    """Check if the function wants any arguments
    """

    argspec = inspect.getfullargspec(f)

    return bool(argspec.args or argspec.varargs or argspec.varkw)


def get_arg_default(f, position):
    sig = inspect.signature(f)
    arg = list(sig.parameters.values())[position]
    arg_def = arg.default
    return arg_def if arg_def != inspect.Parameter.empty else None


# Used to remove control characters and whitespace from cache keys.
valid_chars = set(string.ascii_letters + string.digits + "_.")
delchars = "".join(c for c in map(chr, range(256)) if c not in valid_chars)

null_control = (dict((k, None) for k in delchars),)


def function_namespace(f, args=None):
    """Attempts to returns unique namespace for function"""
    m_args = get_arg_names(f)

    instance_token = None

    instance_self = getattr(f, "__self__", None)

    if instance_self and not inspect.isclass(instance_self):
        instance_token = get_id(f.__self__)
    elif m_args and m_args[0] == "self" and args:
        instance_token = get_id(args[0])

    module = f.__module__

    if m_args and m_args[0] == "cls" and not inspect.isclass(args[0]):
        raise ValueError(
            "When using `delete_memoized` on a "
            "`@classmethod` you must provide the "
            "class as the first argument"
        )

    if hasattr(f, "__qualname__"):
        name = f.__qualname__
    else:
        klass = getattr(f, "__self__", None)

        if klass and not inspect.isclass(klass):
            klass = klass.__class__

        if not klass:
            klass = getattr(f, "im_class", None)

        if not klass:
            if m_args and args:
                if m_args[0] == "self":
                    klass = args[0].__class__
                elif m_args[0] == "cls":
                    klass = args[0]

        if klass:
            name = klass.__name__ + "." + f.__name__
        else:
            name = f.__name__

    ns = ".".join((module, name))
    ns = ns.translate(*null_control)

    if instance_token:
        ins = ".".join((module, name, instance_token))
        ins = ins.translate(*null_control)
    else:
        ins = None

    return ns, ins
