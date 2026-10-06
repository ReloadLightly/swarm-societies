"""A deliberately small, bounded Python language for inherited programs.

This is defense in depth, not an OS security boundary. Evaluate generated programs
in a resource-limited subprocess; no candidate receives simulator objects.
"""
from __future__ import annotations
import ast
import hashlib
import json
from pathlib import Path
import sys


class CandidateError(ValueError):
    pass


SAFE_BUILTINS = {name: __builtins__[name] if isinstance(__builtins__, dict) else getattr(__builtins__, name)
                 for name in ('abs', 'all', 'any', 'bool', 'dict', 'enumerate', 'float', 'int', 'len',
                              'list', 'max', 'min', 'range', 'reversed', 'round', 'sorted', 'str',
                              'sum', 'tuple', 'zip')}
SAFE_METHODS = {'get', 'keys', 'values', 'items', 'copy', 'append', 'extend', 'pop', 'update',
                'setdefault', 'count', 'index', 'sort', 'reverse'}
FORBIDDEN = (ast.Import, ast.ImportFrom, ast.ClassDef, ast.Global, ast.Nonlocal, ast.With,
             ast.AsyncWith, ast.AsyncFunctionDef, ast.Await, ast.Yield, ast.YieldFrom,
             ast.Delete, ast.Try, ast.Raise, ast.Pow, ast.LShift, ast.RShift)


def clean_json(value, limit=32768):
    try:
        raw = json.dumps(value, allow_nan=False, separators=(',', ':'))
        if len(raw) > limit:
            raise CandidateError('candidate state/output exceeds byte limit')
        return json.loads(raw)
    except (TypeError, ValueError, RecursionError) as exc:
        raise CandidateError(f'candidate returned nonfinite or non-JSON data: {exc}') from exc


class CandidateProgram:
    def __init__(self, source: str, name: str = '<candidate>'):
        self.source, self.name = source, name
        self.digest = hashlib.sha256(source.encode()).hexdigest()
        if len(source) > 60000:
            raise CandidateError('candidate source exceeds 60 KB')
        try:
            tree = ast.parse(source, filename=name)
        except SyntaxError as exc:
            raise CandidateError(str(exc)) from exc
        for node in ast.walk(tree):
            if isinstance(node, FORBIDDEN):
                raise CandidateError(f'unsupported syntax: {type(node).__name__}')
            if isinstance(node, ast.Name) and node.id.startswith('_'):
                raise CandidateError('private names are unavailable')
            if isinstance(node, ast.Attribute) and node.attr not in SAFE_METHODS:
                raise CandidateError(f'attribute unavailable: {node.attr}')
            if isinstance(node, ast.FunctionDef) and (node.decorator_list or node.name.startswith('_')):
                raise CandidateError('decorators/private functions are unavailable')
            if isinstance(node, ast.Constant) and isinstance(node.value, (str, bytes)) and len(node.value) > 10000:
                raise CandidateError('oversized constant')
        # Module scope cannot execute arbitrary work or acquire external state.
        for node in tree.body:
            if isinstance(node, ast.FunctionDef):
                if node.args.defaults or node.args.kw_defaults or node.returns or any(a.annotation for a in node.args.args):
                    raise CandidateError('function defaults/annotations unavailable')
            elif isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant):
                pass
            elif isinstance(node, ast.Assign):
                try:
                    ast.literal_eval(node.value)
                except Exception as exc:
                    raise CandidateError('module assignments must be literals') from exc
            else:
                raise CandidateError('module scope permits functions and literal constants only')
        self.namespace = {'__builtins__': SAFE_BUILTINS.copy()}
        exec(compile(tree, name, 'exec'), self.namespace)
        for func in ('member_policy', 'institution'):
            if not callable(self.namespace.get(func)):
                raise CandidateError(f'missing function {func}')

    @classmethod
    def from_path(cls, path):
        return cls(Path(path).read_text(), str(path))

    def fresh(self):
        return CandidateProgram(self.source, self.name)

    def call(self, function, observation, state, max_lines=10000):
        remaining = max_lines
        def guard(frame, event, arg):
            nonlocal remaining
            if frame.f_code.co_filename != self.name:
                return None
            if event == 'line':
                remaining -= 1
                if remaining < 0:
                    raise CandidateError('candidate execution line budget exhausted')
            return guard
        copied_observation, copied_state = clean_json(observation), clean_json(state)
        previous = sys.gettrace()
        try:
            sys.settrace(guard)
            result = self.namespace[function](copied_observation, copied_state)
        except CandidateError:
            raise
        except Exception as exc:
            raise CandidateError(f'{function}: {type(exc).__name__}: {exc}') from exc
        finally:
            sys.settrace(previous)
        if not isinstance(result, dict):
            raise CandidateError(f'{function} must return a dictionary')
        return clean_json(result)


def as_program(value):
    return value.fresh() if isinstance(value, CandidateProgram) else CandidateProgram.from_path(value)
