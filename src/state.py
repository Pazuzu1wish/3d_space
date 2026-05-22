class State:
    """Base class for all game states.
    
    Provides standard lifecycle hooks and loop hooks for event handling,
    updating, and drawing.
    """
    def __init__(self, context):
        self.context = context

    def on_enter(self, manager):
        """Called when this state is pushed onto the stack."""
        pass

    def on_exit(self, manager):
        """Called when this state is popped off the stack."""
        pass

    def handle_event(self, event):
        """Called for every pygame event."""
        pass

    def update(self, dt, manager):
        """Called every frame to update state logic."""
        pass

    def draw(self, screen):
        """Called every frame to draw state visuals."""
        pass


class StateManager:
    """Manages the lifecycle and stack of active game states."""
    def __init__(self, context):
        self.context = context
        self.stack = []

    @property
    def current(self):
        """Returns the current active state at the top of the stack, or None if empty."""
        return self.stack[-1] if self.stack else None

    def push(self, state):
        """Pushes a new state onto the stack and enters it."""
        self.stack.append(state)
        state.on_enter(self)

    def pop(self):
        """Pops the top state off the stack and exits it, returning it."""
        if self.stack:
            state = self.stack.pop()
            state.on_exit(self)
            return state
        return None

    def change(self, state):
        """Replaces the top state of the stack with a new state."""
        self.pop()
        self.push(state)
