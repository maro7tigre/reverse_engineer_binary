import tkinter as tk
from tkinter import scrolledtext, messagebox, filedialog, ttk
import re
import json
import os

class InputFrame(tk.LabelFrame):
    """Frame for hex data input"""
    def __init__(self, parent, callback):
        super().__init__(parent, text="Input Hex Data", padx=5, pady=5)
        self.callback = callback
        self.highlight_tag = "highlight"
        self.selection_tag = "selection_highlight"  # New tag for selection highlights
        
        # Import button
        button_frame = tk.Frame(self)
        button_frame.pack(fill=tk.X, padx=5, pady=(5, 0))
        import_btn = tk.Button(button_frame, text="Import Binary File", command=self.import_file)
        import_btn.pack(side=tk.LEFT, padx=5)
        
        # Input text area
        self.text_input = scrolledtext.ScrolledText(self, height=8, wrap=tk.WORD)
        self.text_input.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        self.text_input.tag_configure(self.highlight_tag, background="#cc7000", foreground="#ffffff", font=("TkDefaultFont", 10, "bold"))
        self.text_input.tag_configure(self.selection_tag, background="#4a6984", foreground="#ffffff")  # Configure the selection highlight tag
        self.text_input.bind("<<Modified>>", self.on_input_change)
        
        # Bind to selection events
        self.text_input.bind("<ButtonRelease-1>", self.on_selection_change)  # Mouse button release
        self.text_input.bind("<KeyRelease>", self.on_selection_change)      # Keyboard selection changes
    
    def import_file(self):
        """Import and display binary file as hex"""
        file_path = filedialog.askopenfilename(title="Select Binary File", filetypes=[("All Files", "*.*")])
        if file_path:
            try:
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
                    self.highlight_selection(selected_text)
        except tk.TclError:
            # No selection exists
            pass
    
    def highlight_selection(self, text_to_highlight):
        """Highlight all occurrences of the selected text"""
        if not text_to_highlight or text_to_highlight.isspace():
            return
        
        # Escape special regex characters
        escaped_text = re.escape(text_to_highlight)
        
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
            
            start_idx = end_idx
    
    def get_input(self):
        return self.text_input.get("1.0", tk.END).strip()
    
    def highlight_patterns(self, patterns):
        """Highlight matching patterns in input text"""
        self.text_input.tag_remove(self.highlight_tag, "1.0", tk.END)
        
        input_text = self.get_input()
        if not input_text or not patterns:
            return
        
        content = self.text_input.get("1.0", tk.END)
        
        for pattern in patterns:
            clean_pattern = ' '.join(pattern.split())
            pattern_parts = clean_pattern.split()
            regex_pattern = r'\s*'.join([re.escape(part) for part in pattern_parts])
            
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
                self.text_input.tag_add(self.highlight_tag, start_index, end_index)


class ModificationFrame(tk.LabelFrame):
    """Frame for managing replacement rules"""
    def __init__(self, parent, update_callback):
        super().__init__(parent, text="Replacement Rules", padx=5, pady=5)
        self.update_callback = update_callback
        self.replacement_rules = []
        
        # Add rule section
        add_frame = tk.Frame(self)
        add_frame.pack(fill=tk.X, padx=5, pady=5)
        
        tk.Label(add_frame, text="Pattern:").grid(row=0, column=0, padx=5, pady=5)
        self.pattern_entry = tk.Entry(add_frame, width=20)
        self.pattern_entry.grid(row=0, column=1, padx=5, pady=5)
        
        tk.Label(add_frame, text="Replace with:").grid(row=0, column=2, padx=5, pady=5)
        self.replace_entry = tk.Entry(add_frame, width=20)
        self.replace_entry.grid(row=0, column=3, padx=5, pady=5)
        
        tk.Button(add_frame, text="Add Rule", command=self.add_rule).grid(row=0, column=4, padx=5, pady=5)
        
        # Save/Load buttons
        button_frame = tk.Frame(self)
        button_frame.pack(fill=tk.X, padx=5, pady=(0, 5))
        
        tk.Button(button_frame, text="Save Rules", command=self.save_rules).pack(side=tk.LEFT, padx=5, pady=5)
        tk.Button(button_frame, text="Load Rules", command=self.load_rules).pack(side=tk.LEFT, padx=5, pady=5)
        
        # Scrollable rules list
        container = tk.Frame(self)
        container.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        scrollbar = tk.Scrollbar(container)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.canvas = tk.Canvas(container)
        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        scrollbar.config(command=self.canvas.yview)
        self.canvas.config(yscrollcommand=scrollbar.set)
        
        self.rules_list_frame = tk.Frame(self.canvas)
        self.canvas_window = self.canvas.create_window((0, 0), window=self.rules_list_frame, anchor="nw")
        
        self.rules_list_frame.bind("<Configure>", self.on_frame_configure)
        self.canvas.bind("<Configure>", self.on_canvas_configure)
        
        tk.Label(self.rules_list_frame, text="").pack()
    
    def save_rules(self):
        """Save rules to JSON file"""
        if not self.replacement_rules:
            messagebox.showwarning("Warning", "No rules to save")
            return
            
        file_path = filedialog.asksaveasfilename(
            title="Save Replacement Rules",
            defaultextension=".json",
            filetypes=[("JSON Files", "*.json"), ("All Files", "*.*")]
        )
        
        if file_path:
            try:
                with open(file_path, 'w') as file:
                    json.dump(self.replacement_rules, file, indent=2)
                messagebox.showinfo("Save Successful", f"Rules saved to {os.path.basename(file_path)}")
            except Exception as e:
                messagebox.showerror("Save Error", f"Error saving rules: {str(e)}")
    
    def load_rules(self):
        """Load rules from JSON file"""
        file_path = filedialog.askopenfilename(
            title="Load Replacement Rules",
            filetypes=[("JSON Files", "*.json"), ("All Files", "*.*")]
        )
        
        if file_path:
            try:
                with open(file_path, 'r') as file:
                    rules = json.load(file)
                    
                if not isinstance(rules, list):
                    raise ValueError("Invalid rule format")
                    
                for rule in rules:
                    if not isinstance(rule, list) or len(rule) != 2:
                        raise ValueError("Invalid rule format")
                        
                self.replacement_rules = rules
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
            self.update_rules_display()
            self.pattern_entry.delete(0, tk.END)
            self.replace_entry.delete(0, tk.END)
            self.update_callback()
        else:
            messagebox.showwarning("Warning", "Both pattern and replacement must be provided")
    
    def update_rules_display(self):
        """Update the visual display of all rules"""
        for widget in self.rules_list_frame.winfo_children():
            widget.destroy()
        
        for idx, (pattern, replacement) in enumerate(self.replacement_rules):
            rule_frame = tk.Frame(self.rules_list_frame, relief=tk.GROOVE, bd=1)
            rule_frame.pack(fill=tk.X, padx=5, pady=2)
            
            tk.Label(rule_frame, text=f"{idx+1}.", width=3).pack(side=tk.LEFT, padx=5, pady=5)
            tk.Label(rule_frame, text=f"Pattern: {pattern}", width=20, anchor="w").pack(side=tk.LEFT, padx=5, pady=5)
            tk.Label(rule_frame, text=f"→ {replacement}", width=20, anchor="w").pack(side=tk.LEFT, padx=5, pady=5)
            
            tk.Button(rule_frame, text="Edit", command=lambda i=idx: self.edit_rule(i)).pack(side=tk.LEFT, padx=5, pady=5)
            tk.Button(rule_frame, text="X", fg="red", command=lambda i=idx: self.delete_rule(i)).pack(side=tk.LEFT, padx=5, pady=5)
        
        if not self.replacement_rules:
            tk.Label(self.rules_list_frame, text="").pack()
            
        self.on_frame_configure(None)
    
    def edit_rule(self, idx):
        """Edit an existing rule"""
        pattern, replacement = self.replacement_rules[idx]
        
        edit_dialog = tk.Toplevel(self)
        edit_dialog.title("Edit Rule")
        edit_dialog.geometry("400x120")
        edit_dialog.resizable(False, False)
        edit_dialog.transient(self)
        edit_dialog.grab_set()
        
        tk.Label(edit_dialog, text="Pattern:").grid(row=0, column=0, padx=10, pady=10, sticky="w")
        pattern_entry = tk.Entry(edit_dialog, width=25)
        pattern_entry.grid(row=0, column=1, padx=10, pady=10)
        pattern_entry.insert(0, pattern)
        
        tk.Label(edit_dialog, text="Replace with:").grid(row=1, column=0, padx=10, pady=10, sticky="w")
        replace_entry = tk.Entry(edit_dialog, width=25)
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
        
        tk.Button(edit_dialog, text="Save", command=save_changes).grid(row=2, column=0, columnspan=2, pady=10)
    
    def delete_rule(self, idx):
        del self.replacement_rules[idx]
        self.update_rules_display()
        self.update_callback()
    
    def get_rules(self):
        return self.replacement_rules


class OutputFrame(tk.LabelFrame):
    """Frame for displaying transformed output"""
    def __init__(self, parent):
        super().__init__(parent, text="Transformed Output", padx=5, pady=5)
        self.highlight_tag = "highlight"
        
        self.text_output = scrolledtext.ScrolledText(self, height=8, wrap=tk.WORD)
        self.text_output.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        self.text_output.config(state=tk.DISABLED)
        
        self.text_output.tag_configure(self.highlight_tag, background="#cc7000", foreground="#ffffff", font=("TkDefaultFont", 10, "bold"))
    
    def set_output(self, text, replacements=None):
        """Set output text with optional highlighting"""
        self.text_output.config(state=tk.NORMAL)
        self.text_output.delete("1.0", tk.END)
        self.text_output.insert("1.0", text)
        
        if replacements:
            for _, replacement in replacements:
                # Skip highlighting escape sequences
                if '\\n' not in replacement and '\\t' not in replacement and '\\r' not in replacement:
                    self.highlight_text(replacement)
                else:
                    # Highlight non-escape parts
                    parts = re.split(r'(\\n|\\t|\\r)', replacement)
                    for part in parts:
                        if part and part not in ['\\n', '\\t', '\\r']:
                            self.highlight_text(part)
                
        self.text_output.config(state=tk.DISABLED)
    
    def highlight_text(self, text_to_highlight):
        """Highlight all occurrences of text"""
        if not text_to_highlight or text_to_highlight.isspace():
            return
            
        start_idx = "1.0"
        while True:
            start_idx = self.text_output.search(text_to_highlight, start_idx, 
                                             stopindex=tk.END, exact=True)
            if not start_idx:
                break
                
            end_idx = f"{start_idx}+{len(text_to_highlight)}c"
            self.text_output.tag_add(self.highlight_tag, start_idx, end_idx)
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
        # Fix: Use raw strings for escape sequences so they're interpreted correctly
        result = text
        # Double backslash to ensure correct parsing
        result = result.replace('\\n', '\n')  # Now actually creates a newline
        result = result.replace('\\t', '\t')  # Tab character
        result = result.replace('\\r', '\r')  # Carriage return
            
        return result


class HexManipulator(tk.Tk):
    """Main application window"""
    def __init__(self):
        super().__init__()
        self.title("Hex Data Manipulator")
        
        # Set window size
        try:
            self.state('zoomed')  # Windows
        except:
            try:
                self.attributes('-zoomed', True)  # Linux
            except:
                self.geometry(f"{self.winfo_screenwidth()}x{self.winfo_screenheight()}")
        
        # Set theme colors
        self.bg_color = "#2b2b2b"
        self.fg_color = "#e0e0e0"
        self.text_bg = "#383838"
        self.text_fg = "#e0e0e0"
        self.button_bg = "#404040"
        self.button_fg = "#e0e0e0"
        self.highlight_bg = "#505050"
        self.frame_bg = "#333333"
        self.entry_bg = "#383838"
        self.entry_fg = "#e0e0e0"
        
        self.configure(bg=self.bg_color)
        self.apply_theme()
        
        self.processor = HexProcessor()
        self.create_ui()
    
    def apply_theme(self):
        """Apply dark theme to the application"""
        # Configure styles
        style = ttk.Style()
        style.configure('TLabel', background=self.bg_color, foreground=self.fg_color)
        style.configure('TButton', background=self.button_bg, foreground=self.button_fg)
        style.configure('TFrame', background=self.bg_color)
        
        # Apply theme to Tk widgets
        self.option_add("*Background", self.bg_color)
        self.option_add("*Foreground", self.fg_color)
        self.option_add("*Button.Background", self.button_bg)
        self.option_add("*Button.Foreground", self.button_fg)
        self.option_add("*Text.Background", self.text_bg)
        self.option_add("*Text.Foreground", self.text_fg)
        self.option_add("*Entry.Background", self.entry_bg)
        self.option_add("*Entry.Foreground", self.entry_fg)
    
    def create_ui(self):
        """Create the application UI"""
        main_frame = tk.Frame(self, bg=self.bg_color)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Create resizable paned window
        self.paned_window = tk.PanedWindow(main_frame, orient=tk.VERTICAL, 
                                         bg=self.bg_color, 
                                         sashwidth=5, 
                                         sashrelief=tk.RAISED,
                                         sashpad=2)
        self.paned_window.pack(fill=tk.BOTH, expand=True)
        
        # Create and add frames
        self.input_frame = InputFrame(self.paned_window, self.update_output)
        self.modification_frame = ModificationFrame(self.paned_window, self.update_output)
        self.output_frame = OutputFrame(self.paned_window)
        
        self.paned_window.add(self.input_frame, stretch="always", minsize=150)
        self.paned_window.add(self.modification_frame, stretch="always", minsize=200)
        self.paned_window.add(self.output_frame, stretch="always", minsize=150)
        
        # Apply theme recursively
        self.apply_theme_to_widget(main_frame)
    
    def apply_theme_to_widget(self, widget):
        """Apply theme to widget and its children"""
        widget_class = widget.winfo_class()
        
        if widget_class in ('Frame', 'Labelframe', 'TFrame'):
            widget.configure(bg=self.frame_bg)
        elif widget_class == 'Label':
            widget.configure(bg=self.frame_bg, fg=self.fg_color)
        elif widget_class == 'Button':
            widget.configure(bg=self.button_bg, fg=self.button_fg, 
                           activebackground=self.highlight_bg, activeforeground=self.fg_color)
        elif widget_class in ('Entry', 'TEntry'):
            widget.configure(bg=self.entry_bg, fg=self.entry_fg, insertbackground=self.fg_color)
        elif widget_class in ('Text', 'ScrolledText'):
            widget.configure(bg=self.text_bg, fg=self.text_fg, 
                           insertbackground=self.fg_color, selectbackground="#4a6984")
        elif widget_class == 'Canvas':
            widget.configure(bg=self.frame_bg, highlightbackground=self.frame_bg)
        elif widget_class == 'PanedWindow':
            widget.configure(bg=self.highlight_bg)
        
        # Apply to children
        for child in widget.winfo_children():
            self.apply_theme_to_widget(child)
    
    def update_output(self):
        """Process input and update output when changes occur"""
        input_text = self.input_frame.get_input()
        replacement_rules = self.modification_frame.get_rules()
        
        # Highlight patterns in input
        if replacement_rules:
            patterns = [pattern for pattern, _ in replacement_rules]
            self.input_frame.highlight_patterns(patterns)
        
        if input_text:
            processed_text = self.processor.process_hex_data(input_text, replacement_rules)
            self.output_frame.set_output(processed_text, replacement_rules)
        else:
            self.output_frame.set_output("", None)


if __name__ == "__main__":
    app = HexManipulator()
    app.mainloop()