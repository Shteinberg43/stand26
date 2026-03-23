from typing import Dict, Any, List, Optional
from dataclasses import dataclass
from my_types import Type

@dataclass
class Value:
    value: Any
    type: Type

class StackFrame:
    def __init__(self, name: str):
        self.name = name
        self.locals: Dict[str, Value] = {}
        self.return_value: Optional[Value] = None
        self.returned: bool = False

    def __repr__(self):
        return f"<Frame {self.name} locals={list(self.locals.keys())}>"

class CallStack:
    def __init__(self):
        self.frames: List[StackFrame] = []

    def push(self, frame: StackFrame):
        self.frames.append(frame)

    def pop(self) -> StackFrame:
        if not self.frames:
            raise RuntimeError("CallStack empty")
        return self.frames.pop()

    def top(self) -> StackFrame:
        if not self.frames:
            raise RuntimeError("CallStack empty")
        return self.frames[-1]

class Environment:
    def __init__(self):
        self.callstack = CallStack()
        self.callstack.push(StackFrame('<global>'))

    def declare_var(self, name: str, value: Value):
        # Переменная всегда объявляется в текущем (верхнем) фрейме
        self.callstack.top().locals[name] = value

    def set_var(self, name: str, value: Value):
        top_frame = self.callstack.top()
        global_frame = self.callstack.frames[0]

        if name in top_frame.locals:
            top_frame.locals[name] = value
        elif top_frame is not global_frame and name in global_frame.locals:
            global_frame.locals[name] = value
        else:
            raise NameError(f"Cannot assign to undeclared variable '{name}'")

    def get_var(self, name: str) -> Value:
        top_frame = self.callstack.top()
        global_frame = self.callstack.frames[0]

        if name in top_frame.locals:
            return top_frame.locals[name]
            
        if top_frame is not global_frame and name in global_frame.locals:
            return global_frame.locals[name]
            
        raise NameError(f"Variable '{name}' not found at runtime")

    def push_frame(self, name: str) -> StackFrame:
        f = StackFrame(name)
        self.callstack.push(f)
        return f

    def pop_frame(self) -> StackFrame:
        return self.callstack.pop()
