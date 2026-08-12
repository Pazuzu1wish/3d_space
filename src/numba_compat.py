from numba import njit as _numba_njit


def njit(*jit_args, **jit_kwargs):
    """Numba njit wrapper that falls back when on-disk caching is unavailable."""
    if jit_args and callable(jit_args[0]) and len(jit_args) == 1 and not jit_kwargs:
        return _compile(jit_args[0], (), {})

    def decorator(func):
        return _compile(func, jit_args, jit_kwargs)

    return decorator


def _compile(func, jit_args, jit_kwargs):
    try:
        return _numba_njit(*jit_args, **jit_kwargs)(func)
    except RuntimeError as exc:
        if jit_kwargs.get("cache") and "cannot cache function" in str(exc):
            fallback_kwargs = dict(jit_kwargs)
            fallback_kwargs["cache"] = False
            return _numba_njit(*jit_args, **fallback_kwargs)(func)
        raise
