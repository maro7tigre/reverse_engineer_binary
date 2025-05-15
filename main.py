import tkinter as tk
from tkinter import scrolledtext, messagebox, filedialog, colorchooser
import ttkbootstrap as tb
import re
import json
import os
import pickle

# Paths for storing application settings
APP_DATA_DIR = os.path.join(os.path.expanduser('~'), '.hex_manipulator')
SETTINGS_FILE = os.path.join(APP_DATA_DIR, 'settings.pkl')

# Ensure the data directory exists
os.makedirs(APP_DATA_DIR, exist_ok=True)

class InputFrame(tb.LabelFrame):
    """Frame for hex data input"""
    def __init__(self, parent, callback):
        super().__init__(parent, text="Input Hex Data")
        self.callback = callback
        self.highlight_tag = "highlight"
        self.selection_tag = "selection_highlight"
        
        # Import button and occurrence counter
        button_frame = tb.Frame(self)
        button_frame.pack(fill=tk.X, padx=5, pady=(5, 0))
        import_btn = tb.Button(button_frame, text="Import Binary File", command=self.import_file)
        import_btn.pack(side=tk.LEFT, padx=5)
        
        # Add occurrence counter label
        self.occurrence_label = tb.Label(button_frame, text="Occurrences: 0")
        self.occurrence_label.pack(side=tk.RIGHT, padx=5)
        
        # Input text area with scrollbar
        self.text_input = scrolledtext.ScrolledText(self, height=8, wrap=tk.WORD)
        self.text_input.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Configure tags for highlighting
        self.text_input.tag_configure(self.highlight_tag, background="#cc7000", foreground="white", font=("TkDefaultFont", 10, "bold"))
        self.text_input.tag_configure(self.selection_tag, background="#4a6984", foreground="white")
        
        self.text_input.bind("<<Modified>>", self.on_input_change)
        self.text_input.bind("<ButtonRelease-1>", self.on_selection_change)
        self.text_input.bind("<KeyRelease>", self.on_selection_change)
    
    def import_file(self):
        """Import and display binary file as hex"""
        # Use the binary files directory from settings
        initial_dir = HexManipulator.app_settings.get('binary_dir', os.path.expanduser('~'))
        
        file_path = filedialog.askopenfilename(
            title="Select Binary File", 
            filetypes=[("All Files", "*.*")],
            initialdir=initial_dir
        )
        
        if file_path:
            try:
                # Update the binary directory in settings
                HexManipulator.app_settings['binary_dir'] = os.path.dirname(file_path)
                HexManipulator.save_settings()
                
                with open(file_path, 'rb') as file:
                    binary_data = file.read()
                hex_str = ' '.join(f'{b:02X}' for b in binary_data)
                self.text_input.delete("1.0", tk.END)
                self.text_input.insert("1.0", hex_str)
                self.callback()
                messagebox.showinfo("Import Successful", f"File '{os.path.basename(file_path)}' imported successfully")
            except Exception as e:
                messagebox.showerror("Import Error", f"Error importing file: {str(e)}")
    
    def on_input_change(self, event=None):
        if self.text_input.edit_modified():
            self.callback()
            self.text_input.edit_modified(False)
    
    def on_selection_change(self, event=None):
        """Handle text selection changes"""
        try:
            # Clear previous selection highlights
            self.text_input.tag_remove(self.selection_tag, "1.0", tk.END)
            
            # Get the selected text
            if self.text_input.tag_ranges(tk.SEL):
                selected_text = self.text_input.get(tk.SEL_FIRST, tk.SEL_LAST)
                
                # Only proceed if we have meaningful selection
                if selected_text and len(selected_text.strip()) > 0:
                    occurrence_count = self.highlight_selection(selected_text)
                    self.occurrence_label.config(text=f"Occurrences: {occurrence_count}")
                else:
                    self.occurrence_label.config(text="Occurrences: 0")
            else:
                self.occurrence_label.config(text="Occurrences: 0")
        except tk.TclError:
            # No selection exists
            self.occurrence_label.config(text="Occurrences: 0")
    
    def highlight_selection(self, text_to_highlight):
        """Highlight all occurrences of the selected text and return count"""
        if not text_to_highlight or text_to_highlight.isspace():
            return 0
        
        # Escape special regex characters
        escaped_text = re.escape(text_to_highlight)
        
        # Count for occurrences
        occurrence_count = 0
        
        # Highlight all occurrences
        start_idx = "1.0"
        while True:
            start_idx = self.text_input.search(escaped_text, start_idx, 
                                             stopindex=tk.END, 
                                             regexp=True,
                                             nocase=False)
            if not start_idx:
                break
                
            end_idx = f"{start_idx}+{len(text_to_highlight)}c"
            
            # Don't apply tag to the current selection to avoid tag conflict
            if not (self.text_input.tag_ranges(tk.SEL) and 
                   start_idx == self.text_input.index(tk.SEL_FIRST) and 
                   end_idx == self.text_input.index(tk.SEL_LAST)):
                self.text_input.tag_add(self.selection_tag, start_idx, end_idx)
                occurrence_count += 1
            
            start_idx = end_idx
        
        return occurrence_count
    
    def get_input(self):
        return self.text_input.get("1.0", tk.END).strip()
    
    def highlight_patterns(self, patterns, colors=None):
        """Highlight matching patterns in input text with custom colors"""
        # Clear all previous highlight tags
        for tag in self.text_input.tag_names():
            if tag.startswith("color_") or tag == self.highlight_tag:
                self.text_input.tag_remove(tag, "1.0", tk.END)
        
        input_text = self.get_input()
        if not input_text or not patterns:
            return
        
        content = self.text_input.get("1.0", tk.END)
        
        for i, pattern in enumerate(patterns):
            clean_pattern = ' '.join(pattern.split())
            pattern_parts = clean_pattern.split()
            regex_pattern = r'\s*'.join([re.escape(part) for part in pattern_parts])
            
            # Get color for this pattern
            color = "#cc7000"  # Default color
            if colors and i < len(colors) and colors[i]:
                color = colors[i]
            
            # Create a unique tag for this color if it doesn't exist
            tag_name = f"color_{i}"
            if tag_name not in self.text_input.tag_names():
                self.text_input.tag_configure(tag_name, background=color, foreground="white", font=("TkDefaultFont", 10, "bold"))
            else:
                # Update existing tag's color
                self.text_input.tag_configure(tag_name, background=color)
            
            for match in re.finditer(regex_pattern, content):
                start_pos = match.start()
                end_pos = match.end()
                
                # Convert byte offset to line.char format
                start_line = content[:start_pos].count('\n') + 1
                start_char = start_pos - content[:start_pos].rfind('\n') - 1
                if start_line == 1:
                    start_char = start_pos
                
                end_line = content[:end_pos].count('\n') + 1
                end_char = end_pos - content[:end_pos].rfind('\n') - 1
                if end_line == 1:
                    end_char = end_pos
                
                # Apply tag
                start_index = f"{start_line}.{start_char}"
                end_index = f"{end_line}.{end_char}"
                self.text_input.tag_add(tag_name, start_index, end_index)


class ColorSquare(tk.Frame):
    """Custom widget for a clickable color square"""
    def __init__(self, parent, color="#cc7000", size=24, command=None):
        super().__init__(parent, width=size, height=size, bd=1, relief=tk.SUNKEN)
        self.color = color
        self.command = command
        self.size = size
        
        # Ensure the frame stays the specified size
        self.grid_propagate(False)
        self.pack_propagate(False)
        
        # Force tk to use our background color, not ttk theme
        self.config(background="white")
        
        # Create the color panel - ensure it gets a specific background color
        self.color_panel = tk.Label(self, background=color)
        self.color_panel.pack(fill=tk.BOTH, expand=True)
        
        # Bind click event
        self.color_panel.bind("<Button-1>", self._on_click)
        self.bind("<Button-1>", self._on_click)
    
    def _on_click(self, event):
        if self.command:
            self.command()
    
    def set_color(self, color):
        # Update stored color
        self.color = color
        # Update visual appearance 
        self.color_panel.config(background=color)


class ModificationFrame(tb.LabelFrame):
    """Frame for managing replacement rules"""
    def __init__(self, parent, update_callback):
        super().__init__(parent, text="Replacement Rules")
        self.update_callback = update_callback
        self.replacement_rules = []
        self.rule_colors = []  # Store colors for each rule
        self.DEFAULT_COLOR = "#cc7000"  # Orange default color
        
        # Add rule section
        add_frame = tb.Frame(self)
        add_frame.pack(fill=tk.X, padx=5, pady=5)
        
        tb.Label(add_frame, text="Pattern:").grid(row=0, column=0, padx=5, pady=5)
        self.pattern_entry = tb.Entry(add_frame, width=20)
        self.pattern_entry.grid(row=0, column=1, padx=5, pady=5)
        
        tb.Label(add_frame, text="Replace with:").grid(row=0, column=2, padx=5, pady=5)
        self.replace_entry = tb.Entry(add_frame, width=20)
        self.replace_entry.grid(row=0, column=3, padx=5, pady=5)
        
        # Color selector for new rules - explicitly set to orange
        self.color_selector = ColorSquare(add_frame, color=self.DEFAULT_COLOR, command=self.select_color)
        self.color_selector.grid(row=0, column=4, padx=5, pady=5)
        self.color_selector.set_color(self.DEFAULT_COLOR)  # Ensure color is set
        
        # Add rule button
        tb.Button(add_frame, text="Add Rule", command=self.add_rule).grid(row=0, column=5, padx=5, pady=5)
        
        # Save/Load buttons
        button_frame = tb.Frame(self)
        button_frame.pack(fill=tk.X, padx=5, pady=(0, 5))
        
        tb.Button(button_frame, text="Save Rules", command=self.save_rules).pack(side=tk.LEFT, padx=5, pady=5)
        tb.Button(button_frame, text="Load Rules", command=self.load_rules).pack(side=tk.LEFT, padx=5, pady=5)
        
        # Scrollable rules list
        container = tb.Frame(self)
        container.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        self.scrollbar = tb.Scrollbar(container)
        self.scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.canvas = tk.Canvas(container)
        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        self.scrollbar.config(command=self.canvas.yview)
        self.canvas.config(yscrollcommand=self.scrollbar.set)
        
        self.rules_list_frame = tb.Frame(self.canvas)
        self.canvas_window = self.canvas.create_window((0, 0), window=self.rules_list_frame, anchor="nw")
        
        self.rules_list_frame.bind("<Configure>", self.on_frame_configure)
        self.canvas.bind("<Configure>", self.on_canvas_configure)
        
        # Initial empty label to ensure proper layout
        tb.Label(self.rules_list_frame, text="").pack()
    
    def select_color(self):
        """Open color chooser dialog and update color selector"""
        current_color = self.color_selector.get_color()
        color_result = colorchooser.askcolor(initialcolor=current_color)
        
        if color_result and color_result[1]:  # color_result[1] is the hex string
            self.color_selector.set_color(color_result[1])
    
    def save_rules(self):
        """Save rules to JSON file with color information"""
        if not self.replacement_rules:
            messagebox.showwarning("Warning", "No rules to save")
            return
            
        # Use the rules directory from settings
        initial_dir = HexManipulator.app_settings.get('rules_dir', os.path.expanduser('~'))
        
        file_path = filedialog.asksaveasfilename(
            title="Save Replacement Rules",
            defaultextension=".json",
            filetypes=[("JSON Files", "*.json"), ("All Files", "*.*")],
            initialdir=initial_dir
        )
        
        if file_path:
            try:
                # Update the rules directory in settings
                HexManipulator.app_settings['rules_dir'] = os.path.dirname(file_path)
                HexManipulator.save_settings()
                
                # Create a list of rules with their colors
                rules_with_colors = []
                for i, rule in enumerate(self.replacement_rules):
                    color = self.rule_colors[i] if i < len(self.rule_colors) else self.DEFAULT_COLOR
                    rules_with_colors.append({
                        "pattern": rule[0],
                        "replacement": rule[1],
                        "color": color
                    })
                
                with open(file_path, 'w') as file:
                    json.dump(rules_with_colors, file, indent=2)
                messagebox.showinfo("Save Successful", f"Rules saved to {os.path.basename(file_path)}")
            except Exception as e:
                messagebox.showerror("Save Error", f"Error saving rules: {str(e)}")
    
    def load_rules(self):
        """Load rules from JSON file with color information"""
        # Use the rules directory from settings
        initial_dir = HexManipulator.app_settings.get('rules_dir', os.path.expanduser('~'))
        
        file_path = filedialog.askopenfilename(
            title="Load Replacement Rules",
            filetypes=[("JSON Files", "*.json"), ("All Files", "*.*")],
            initialdir=initial_dir
        )
        
        if file_path:
            try:
                # Update the rules directory in settings
                HexManipulator.app_settings['rules_dir'] = os.path.dirname(file_path)
                HexManipulator.save_settings()
                
                with open(file_path, 'r') as file:
                    data = json.load(file)
                    
                self.replacement_rules = []
                self.rule_colors = []
                
                # Handle both old and new format
                if isinstance(data, list):
                    if all(isinstance(item, list) for item in data):
                        # Old format without colors
                        self.replacement_rules = data
                        self.rule_colors = [self.DEFAULT_COLOR] * len(data)  # Default color for all
                    else:
                        # New format with colors
                        for rule_data in data:
                            if isinstance(rule_data, dict) and "pattern" in rule_data and "replacement" in rule_data:
                                self.replacement_rules.append([rule_data["pattern"], rule_data["replacement"]])
                                # Use default color if not specified
                                self.rule_colors.append(rule_data.get("color", self.DEFAULT_COLOR))
                            else:
                                raise ValueError("Invalid rule format")
                else:
                    raise ValueError("Invalid rule format")
                        
                self.update_rules_display()
                self.update_callback()
                messagebox.showinfo("Load Successful", f"Rules loaded from {os.path.basename(file_path)}")
            except Exception as e:
                messagebox.showerror("Load Error", f"Error loading rules: {str(e)}")
    
    def on_frame_configure(self, event):
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))
    
    def on_canvas_configure(self, event):
        self.canvas.itemconfig(self.canvas_window, width=event.width)
    
    def add_rule(self):
        pattern = self.pattern_entry.get().strip()
        replacement = self.replace_entry.get().strip()
        
        if pattern and replacement:
            self.replacement_rules.append([pattern, replacement])
            # Get the current color from the color selector
            self.rule_colors.append(self.color_selector.get_color())
            self.update_rules_display()
            self.pattern_entry.delete(0, tk.END)
            self.replace_entry.delete(0, tk.END)
            # Keep the color selector's color for the next rule
            self.update_callback()
        else:
            messagebox.showwarning("Warning", "Both pattern and replacement must be provided")
    
    def update_rules_display(self):
        """Update the visual display of all rules"""
        # Clear all existing widgets
        for widget in self.rules_list_frame.winfo_children():
            widget.destroy()
        
        # Create a dictionary to store color square widgets
        self.color_squares = {}
        
        for idx, (pattern, replacement) in enumerate(self.replacement_rules):
            rule_frame = tb.Frame(self.rules_list_frame)
            rule_frame.pack(fill=tk.X, padx=5, pady=2)
            
            # Get color for this rule - ensure default orange for any without a color
            color = self.DEFAULT_COLOR  # Default orange
            if idx < len(self.rule_colors) and self.rule_colors[idx]:
                color = self.rule_colors[idx]
            else:
                # If this rule doesn't have a color, add the default
                if idx >= len(self.rule_colors):
                    self.rule_colors.append(self.DEFAULT_COLOR)
                elif not self.rule_colors[idx]:
                    self.rule_colors[idx] = self.DEFAULT_COLOR
                color = self.DEFAULT_COLOR
            
            tb.Label(rule_frame, text=f"{idx+1}.", width=3).pack(side=tk.LEFT, padx=5, pady=5)
            tb.Label(rule_frame, text=f"Pattern: {pattern}", width=20, anchor="w").pack(side=tk.LEFT, padx=5, pady=5)
            tb.Label(rule_frame, text=f"→ {replacement}", width=20, anchor="w").pack(side=tk.LEFT, padx=5, pady=5)
            
            # Create color square for this rule with explicit background
            def make_color_command(rule_idx):
                return lambda: self.edit_color(rule_idx)
            
            # Create a new color square widget and explicitly set its color
            color_square = ColorSquare(rule_frame, color=color, command=make_color_command(idx))
            color_square.set_color(color)  # Explicitly call set_color with the current color
            color_square.pack(side=tk.LEFT, padx=5, pady=5)
            
            # Store reference to this color square
            self.color_squares[idx] = color_square
            
            tb.Button(rule_frame, text="Edit", command=lambda i=idx: self.edit_rule(i)).pack(side=tk.LEFT, padx=5, pady=5)
            tb.Button(rule_frame, text="X", command=lambda i=idx: self.delete_rule(i)).pack(side=tk.LEFT, padx=5, pady=5)
        
        if not self.replacement_rules:
            tb.Label(self.rules_list_frame, text="").pack()
            
        self.on_frame_configure(None)
    
    def edit_color(self, idx):
        """Edit color for a rule"""
        # Get current color
        current_color = self.rule_colors[idx] if idx < len(self.rule_colors) else self.DEFAULT_COLOR
        
        # Open color chooser
        color_result = colorchooser.askcolor(initialcolor=current_color)
        
        if color_result and color_result[1]:  # color_result[1] is the hex string
            new_color = color_result[1]
            
            # Update the color in our list
            if idx < len(self.rule_colors):
                self.rule_colors[idx] = new_color
            else:
                # Extend the colors list if needed
                while len(self.rule_colors) <= idx:
                    self.rule_colors.append(self.DEFAULT_COLOR)
                self.rule_colors[idx] = new_color
            
            # If we have a reference to the color square, update it directly
            if hasattr(self, 'color_squares') and idx in self.color_squares:
                self.color_squares[idx].set_color(new_color)
            
            # Update display and highlights
            self.update_rules_display()
            self.update_callback()
    
    def edit_rule(self, idx):
        """Edit an existing rule"""
        pattern, replacement = self.replacement_rules[idx]
        
        edit_dialog = tb.Toplevel(self)
        edit_dialog.title("Edit Rule")
        edit_dialog.geometry("400x120")
        edit_dialog.resizable(False, False)
        edit_dialog.transient(self)
        edit_dialog.grab_set()
        
        tb.Label(edit_dialog, text="Pattern:").grid(row=0, column=0, padx=10, pady=10, sticky="w")
        pattern_entry = tb.Entry(edit_dialog, width=25)
        pattern_entry.grid(row=0, column=1, padx=10, pady=10)
        pattern_entry.insert(0, pattern)
        
        tb.Label(edit_dialog, text="Replace with:").grid(row=1, column=0, padx=10, pady=10, sticky="w")
        replace_entry = tb.Entry(edit_dialog, width=25)
        replace_entry.grid(row=1, column=1, padx=10, pady=10)
        replace_entry.insert(0, replacement)
        
        def save_changes():
            new_pattern = pattern_entry.get().strip()
            new_replacement = replace_entry.get().strip()
            
            if new_pattern and new_replacement:
                self.replacement_rules[idx] = [new_pattern, new_replacement]
                self.update_rules_display()
                edit_dialog.destroy()
                self.update_callback()
            else:
                messagebox.showwarning("Warning", "Both pattern and replacement must be provided")
        
        tb.Button(edit_dialog, text="Save", command=save_changes).grid(row=2, column=0, columnspan=2, pady=10)
    
    def delete_rule(self, idx):
        """Delete a rule and its associated color"""
        del self.replacement_rules[idx]
        
        # Delete the color if it exists
        if idx < len(self.rule_colors):
            del self.rule_colors[idx]
            
        self.update_rules_display()
        self.update_callback()
    
    def get_rules(self):
        return self.replacement_rules
    
    def get_colors(self):
        # Ensure we have colors for all rules
        while len(self.rule_colors) < len(self.replacement_rules):
            self.rule_colors.append(self.DEFAULT_COLOR)
        return self.rule_colors


class OutputFrame(tb.LabelFrame):
    """Frame for displaying transformed output"""
    def __init__(self, parent):
        super().__init__(parent, text="Transformed Output")
        self.DEFAULT_COLOR = "#cc7000"  # Default highlighting color
        
        self.text_output = scrolledtext.ScrolledText(self, height=8, wrap=tk.WORD)
        self.text_output.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        self.text_output.config(state=tk.DISABLED)
    
    def set_output(self, text, replacements=None, colors=None):
        """Set output text with optional highlighting using custom colors"""
        self.text_output.config(state=tk.NORMAL)
        self.text_output.delete("1.0", tk.END)
        self.text_output.insert("1.0", text)
        
        # Remove any existing highlight tags
        for tag in self.text_output.tag_names():
            if tag.startswith("output_color_"):
                self.text_output.tag_remove(tag, "1.0", tk.END)
        
        if replacements:
            for i, (_, replacement) in enumerate(replacements):
                # Get color for this replacement
                color = self.DEFAULT_COLOR
                if colors and i < len(colors) and colors[i]:
                    color = colors[i]
                
                # Create or update tag for this color
                tag_name = f"output_color_{i}"
                if tag_name not in self.text_output.tag_names():
                    self.text_output.tag_configure(tag_name, background=color, foreground="white", font=("TkDefaultFont", 10, "bold"))
                else:
                    self.text_output.tag_configure(tag_name, background=color)
                
                # Skip highlighting escape sequences
                if '\\n' not in replacement and '\\t' not in replacement and '\\r' not in replacement:
                    self.highlight_text(replacement, tag_name)
                else:
                    # Highlight non-escape parts
                    parts = re.split(r'(\\n|\\t|\\r)', replacement)
                    for part in parts:
                        if part and part not in ['\\n', '\\t', '\\r']:
                            self.highlight_text(part, tag_name)
                
        self.text_output.config(state=tk.DISABLED)
    
    def highlight_text(self, text_to_highlight, tag_name):
        """Highlight all occurrences of text with specified tag"""
        if not text_to_highlight or text_to_highlight.isspace():
            return
            
        start_idx = "1.0"
        while True:
            start_idx = self.text_output.search(text_to_highlight, start_idx, 
                                             stopindex=tk.END, exact=True)
            if not start_idx:
                break
                
            end_idx = f"{start_idx}+{len(text_to_highlight)}c"
            self.text_output.tag_add(tag_name, start_idx, end_idx)
            start_idx = end_idx


class HexProcessor:
    """Process hex data with replacement rules"""
    def process_hex_data(self, input_data, replacement_rules):
        """Apply replacement rules to hex data"""
        result = input_data
        
        for pattern, replacement in replacement_rules:
            processed_replacement = self._process_escape_sequences(replacement)
            
            clean_pattern = ' '.join(pattern.split())
            pattern_parts = clean_pattern.split()
            regex_pattern = r'\s*'.join([re.escape(part) for part in pattern_parts])
            
            result = re.sub(regex_pattern, processed_replacement, result)
            
        return result
    
    def _process_escape_sequences(self, text):
        """Process escape sequences in replacement text"""
        result = text
        result = result.replace('\\n', '\n')  # Newline
        result = result.replace('\\t', '\t')  # Tab character
        result = result.replace('\\r', '\r')  # Carriage return
            
        return result


class HexManipulator(tb.Window):
    """Main application window"""
    # Class variable to store app settings
    app_settings = {
        'window_geometry': '',
        'window_is_maximized': False,
        'pane_positions': [],
        'binary_dir': os.path.expanduser('~'),
        'rules_dir': os.path.expanduser('~')
    }
    
    @classmethod
    def load_settings(cls):
        """Load application settings from file"""
        try:
            if os.path.exists(SETTINGS_FILE):
                with open(SETTINGS_FILE, 'rb') as f:
                    cls.app_settings = pickle.load(f)
        except Exception as e:
            print(f"Error loading settings: {str(e)}")
    
    @classmethod
    def save_settings(cls):
        """Save application settings to file"""
        try:
            with open(SETTINGS_FILE, 'wb') as f:
                pickle.dump(cls.app_settings, f)
        except Exception as e:
            print(f"Error saving settings: {str(e)}")
    
    def __init__(self):
        # Load settings before initializing the window
        self.load_settings()
        
        # Initialize the window with ttkbootstrap
        super().__init__(themename="darkly")
        self.title("Hex Data Manipulator")
        
        # Apply saved window state or default to maximized
        if self.app_settings.get('window_is_maximized', True):
            self.state('zoomed')  # Windows maximized state
        elif self.app_settings.get('window_geometry'):
            try:
                self.geometry(self.app_settings['window_geometry'])
            except:
                # Fallback if saved geometry is invalid
                self.geometry('800x600')
        else:
            # Default size
            self.geometry('800x600')
        
        self.processor = HexProcessor()
        self.create_ui()
        
        # Save settings when closing the window
        self.protocol("WM_DELETE_WINDOW", self.on_closing)
    
    def create_ui(self):
        """Create the application UI"""
        main_frame = tb.Frame(self)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Create resizable paned window
        self.paned_window = tk.PanedWindow(main_frame, orient=tk.VERTICAL)
        self.paned_window.pack(fill=tk.BOTH, expand=True)
        
        # Create and add frames
        self.input_frame = InputFrame(self.paned_window, self.update_output)
        self.modification_frame = ModificationFrame(self.paned_window, self.update_output)
        self.output_frame = OutputFrame(self.paned_window)
        
        self.paned_window.add(self.input_frame, stretch="always", minsize=150)
        self.paned_window.add(self.modification_frame, stretch="always", minsize=200)
        self.paned_window.add(self.output_frame, stretch="always", minsize=150)
        
        # Restore pane positions if available
        if self.app_settings.get('pane_positions') and len(self.app_settings['pane_positions']) == 2:
            try:
                positions = self.app_settings['pane_positions']
                self.update_idletasks()  # Ensure UI is rendered before setting positions
                self.paned_window.sash_place(0, 0, positions[0])
                self.paned_window.sash_place(1, 0, positions[1])
            except Exception as e:
                print(f"Error restoring pane positions: {str(e)}")
    
    def update_output(self):
        """Process input and update output when changes occur"""
        input_text = self.input_frame.get_input()
        replacement_rules = self.modification_frame.get_rules()
        rule_colors = self.modification_frame.get_colors()
        
        # Highlight patterns in input
        if replacement_rules:
            patterns = [pattern for pattern, _ in replacement_rules]
            self.input_frame.highlight_patterns(patterns, rule_colors)
        
        if input_text:
            processed_text = self.processor.process_hex_data(input_text, replacement_rules)
            self.output_frame.set_output(processed_text, replacement_rules, rule_colors)
        else:
            self.output_frame.set_output("", None)
    
    def on_closing(self):
        """Save settings and close the application"""
        # Save window state
        self.app_settings['window_is_maximized'] = (self.state() == 'zoomed')
        
        # If not maximized, save the window geometry
        if not self.app_settings['window_is_maximized']:
            self.app_settings['window_geometry'] = self.geometry()
        
        # Save pane positions
        try:
            positions = [self.paned_window.sash_coord(i)[1] for i in range(self.paned_window.sash_number())]
            self.app_settings['pane_positions'] = positions
        except:
            pass
        
        # Save all settings
        self.save_settings()
        
        # Close the window
        self.destroy()


if __name__ == "__main__":
    app = HexManipulator()
    app.mainloop()