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

class SimplePatternRule:
    """Represents a pattern rule with visual template and location selection"""
    def __init__(self, pattern_template, replacement, priority=0, 
                 location_enabled=False, selected_part_index=0, color="#cc7000"):
        self.pattern_template = pattern_template  # "## 2A ##"
        self.replacement = replacement
        self.priority = priority
        self.location_enabled = location_enabled
        self.selected_part_index = selected_part_index  # Which ## is selected
        self.color = color
        
    def to_regex(self):
        """Convert template like '## 2A ##' to regex pattern"""
        parts = self.pattern_template.split()
        regex_parts = []
        
        for part in parts:
            if part == "##":
                regex_parts.append(r"(\w{2})")  # Capture group for wildcards
            else:
                regex_parts.append(re.escape(part))
                
        return r"\s+".join(regex_parts)
    
    def get_location_capture_group(self):
        """Returns which regex capture group corresponds to selected location part"""
        if not self.location_enabled:
            return None
            
        wildcard_count = 0
        for part in self.pattern_template.split():
            if part == "##":
                if wildcard_count == self.selected_part_index:
                    return wildcard_count + 1  # Regex groups are 1-indexed
                wildcard_count += 1
        return None
    
    def get_wildcard_count(self):
        """Count number of ## wildcards in template"""
        return self.pattern_template.count("##")
    
    def process_replacement(self, match_groups):
        """Process replacement template with captured groups and arithmetic"""
        result = self.replacement
        
        # Handle arithmetic operations
        for i, group_value in enumerate(match_groups):
            group_num = i + 1
            
            # Handle hex to decimal conversion with arithmetic
            hex_dec_pattern = rf"\{{hex_to_dec\(\${group_num}\)([+\-*/]\d+)?\}}"
            matches = re.findall(hex_dec_pattern, result)
            
            for operation in matches:
                try:
                    decimal_value = int(group_value, 16)
                    if operation:
                        if operation.startswith('+'):
                            decimal_value += int(operation[1:])
                        elif operation.startswith('-'):
                            decimal_value -= int(operation[1:])
                        elif operation.startswith('*'):
                            decimal_value *= int(operation[1:])
                        elif operation.startswith('/'):
                            decimal_value //= int(operation[1:])
                    
                    full_pattern = f"{{hex_to_dec(${group_num}){operation}}}"
                    result = result.replace(full_pattern, str(decimal_value))
                except ValueError:
                    # If conversion fails, leave as is
                    pass
            
            # Handle basic substitutions
            result = result.replace(f"${group_num}", group_value)
        
        return result
    
    def to_dict(self):
        """Convert to dictionary for saving"""
        return {
            "pattern_template": self.pattern_template,
            "replacement": self.replacement,
            "priority": self.priority,
            "location_enabled": self.location_enabled,
            "selected_part_index": self.selected_part_index,
            "color": self.color
        }
    
    @classmethod
    def from_dict(cls, data):
        """Create instance from dictionary"""
        return cls(
            data.get("pattern_template", ""),
            data.get("replacement", ""),
            data.get("priority", 0),
            data.get("location_enabled", False),
            data.get("selected_part_index", 0),
            data.get("color", "#cc7000")
        )


class InputFrame(tb.LabelFrame):
    """Frame for hex data input"""
    def __init__(self, parent, callback):
        super().__init__(parent, text="Input Hex Data")
        self.callback = callback
        self.highlight_tag = "highlight"
        self.selection_tag = "selection_highlight"
        self.rule_tags = []
        
        # Import button and occurrence counter
        button_frame = tb.Frame(self)
        button_frame.pack(fill=tk.X, padx=5, pady=(5, 0))
        import_btn = tb.Button(button_frame, text="Import Binary File", command=self.import_file)
        import_btn.pack(side=tk.LEFT, padx=5)
        
        self.occurrence_label = tb.Label(button_frame, text="Occurrences: 0")
        self.occurrence_label.pack(side=tk.RIGHT, padx=5)
        
        # Input text area
        self.text_input = scrolledtext.ScrolledText(self, height=8, wrap=tk.WORD)
        self.text_input.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Configure tags
        self.text_input.tag_configure(self.highlight_tag, background="#cc7000", foreground="white", font=("TkDefaultFont", 10, "bold"))
        self.text_input.tag_configure(self.selection_tag, background="#4a6984", foreground="white")
        self.text_input.tag_raise(self.selection_tag)
        
        self.text_input.bind("<<Modified>>", self.on_input_change)
        self.text_input.bind("<ButtonRelease-1>", self.on_selection_change)
        self.text_input.bind("<KeyRelease>", self.on_selection_change)
    
    def import_file(self):
        """Import binary file as hex"""
        initial_dir = HexManipulator.app_settings.get('binary_dir', os.path.expanduser('~'))
        
        file_path = filedialog.askopenfilename(
            title="Select Binary File", 
            filetypes=[("All Files", "*.*")],
            initialdir=initial_dir
        )
        
        if file_path:
            try:
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
            self.text_input.tag_remove(self.selection_tag, "1.0", tk.END)
            
            if self.text_input.tag_ranges(tk.SEL):
                selected_text = self.text_input.get(tk.SEL_FIRST, tk.SEL_LAST)
                
                if selected_text and len(selected_text.strip()) > 0:
                    occurrence_count = self.highlight_selection(selected_text)
                    self.occurrence_label.config(text=f"Occurrences: {occurrence_count}")
                else:
                    self.occurrence_label.config(text="Occurrences: 0")
            else:
                self.occurrence_label.config(text="Occurrences: 0")
        except tk.TclError:
            self.occurrence_label.config(text="Occurrences: 0")
    
    def highlight_selection(self, text_to_highlight):
        """Highlight all occurrences of selected text"""
        if not text_to_highlight or text_to_highlight.isspace():
            return 0
        
        escaped_text = re.escape(text_to_highlight)
        occurrence_count = 0
        
        start_idx = "1.0"
        while True:
            start_idx = self.text_input.search(escaped_text, start_idx, 
                                             stopindex=tk.END, 
                                             regexp=True, nocase=False)
            if not start_idx:
                break
                
            end_idx = f"{start_idx}+{len(text_to_highlight)}c"
            self.text_input.tag_add(self.selection_tag, start_idx, end_idx)
            occurrence_count += 1
            start_idx = end_idx
        
        return occurrence_count
    
    def get_input(self):
        return self.text_input.get("1.0", tk.END).strip()
    
    def highlight_patterns(self, pattern_rules):
        """Highlight matching patterns with their colors"""
        # Clear existing rule tags
        for tag in self.rule_tags:
            self.text_input.tag_remove(tag, "1.0", tk.END)
        
        self.rule_tags = []
        input_text = self.get_input()
        
        if not input_text or not pattern_rules:
            return
        
        content = self.text_input.get("1.0", tk.END)
        
        for i, rule in enumerate(pattern_rules):
            try:
                regex_pattern = rule.to_regex()
                tag_name = f"pattern_color_{i}"
                self.rule_tags.append(tag_name)
                
                if tag_name not in self.text_input.tag_names():
                    self.text_input.tag_configure(tag_name, background=rule.color, 
                                                foreground="white", font=("TkDefaultFont", 10, "bold"))
                else:
                    self.text_input.tag_configure(tag_name, background=rule.color)
                
                self.text_input.tag_lower(tag_name, self.selection_tag)
                
                for match in re.finditer(regex_pattern, content):
                    start_pos = match.start()
                    end_pos = match.end()
                    
                    # Convert to line.char format
                    start_line = content[:start_pos].count('\n') + 1
                    start_char = start_pos - content[:start_pos].rfind('\n') - 1
                    if start_line == 1:
                        start_char = start_pos
                    
                    end_line = content[:end_pos].count('\n') + 1
                    end_char = end_pos - content[:end_pos].rfind('\n') - 1
                    if end_line == 1:
                        end_char = end_pos
                    
                    start_index = f"{start_line}.{start_char}"
                    end_index = f"{end_line}.{end_char}"
                    self.text_input.tag_add(tag_name, start_index, end_index)
            
            except re.error:
                # Skip invalid regex patterns
                continue


class ColorSquare(tk.Frame):
    """Clickable color square widget"""
    def __init__(self, parent, color="#cc7000", size=24, command=None):
        super().__init__(parent, width=size, height=size, bd=1, relief=tk.SUNKEN)
        self.color = color
        self.command = command
        self.size = size
        
        self.grid_propagate(False)
        self.pack_propagate(False)
        self.config(background="white")
        
        self.color_panel = tk.Label(self, background=color)
        self.color_panel.pack(fill=tk.BOTH, expand=True)
        
        self.color_panel.bind("<Button-1>", self._on_click)
        self.bind("<Button-1>", self._on_click)
    
    def _on_click(self, event):
        if self.command:
            self.command()
    
    def set_color(self, color):
        self.color = color
        self.color_panel.config(background=color)
    
    def get_color(self):
        return self.color


class PatternRulesFrame(tb.LabelFrame):
    """Frame for pattern rule management with visual template input"""
    def __init__(self, parent, update_callback):
        super().__init__(parent, text="Pattern Rules")
        self.update_callback = update_callback
        self.pattern_rules = []
        self.DEFAULT_COLOR = "#cc7000"
        
        # Add rule section
        add_frame = tb.Frame(self)
        add_frame.pack(fill=tk.X, padx=5, pady=5)
        
        # Row 1: Pattern template and replacement
        tb.Label(add_frame, text="Pattern:").grid(row=0, column=0, padx=5, pady=5, sticky="w")
        self.pattern_entry = tb.Entry(add_frame, width=15)
        self.pattern_entry.grid(row=0, column=1, padx=5, pady=5)
        self.pattern_entry.insert(0, "## ?? ##")
        
        tb.Label(add_frame, text="Replace:").grid(row=0, column=2, padx=5, pady=5, sticky="w")
        self.replace_entry = tb.Entry(add_frame, width=20)
        self.replace_entry.grid(row=0, column=3, padx=5, pady=5)
        
        # Row 2: Priority, color, location checkbox
        tb.Label(add_frame, text="Priority:").grid(row=1, column=0, padx=5, pady=5, sticky="w")
        self.priority_var = tk.IntVar(value=0)
        priority_spinbox = tb.Spinbox(add_frame, from_=-10, to=10, width=5, textvariable=self.priority_var)
        priority_spinbox.grid(row=1, column=1, padx=5, pady=5, sticky="w")
        
        self.color_selector = ColorSquare(add_frame, color=self.DEFAULT_COLOR, command=self.select_color)
        self.color_selector.grid(row=1, column=2, padx=5, pady=5)
        
        self.location_enabled_var = tk.BooleanVar()
        location_check = tb.Checkbutton(add_frame, text="Enable Location", variable=self.location_enabled_var)
        location_check.grid(row=1, column=3, padx=5, pady=5, sticky="w")
        
        # Add button
        tb.Button(add_frame, text="Add Rule", command=self.add_rule).grid(row=1, column=4, padx=5, pady=5)
        
        # Save/Load buttons
        button_frame = tb.Frame(self)
        button_frame.pack(fill=tk.X, padx=5, pady=(0, 5))
        
        tb.Button(button_frame, text="Save Rules", command=self.save_rules).pack(side=tk.LEFT, padx=5, pady=5)
        tb.Button(button_frame, text="Load Rules", command=self.load_rules).pack(side=tk.LEFT, padx=5, pady=5)
        
        # Scrollable rules list
        self.setup_scrollable_list()
    
    def setup_scrollable_list(self):
        """Setup scrollable rules display"""
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
        
        # Initial empty state
        tb.Label(self.rules_list_frame, text="No rules defined").pack()
    
    def on_frame_configure(self, event):
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))
    
    def on_canvas_configure(self, event):
        self.canvas.itemconfig(self.canvas_window, width=event.width)
    
    def select_color(self):
        """Open color chooser dialog"""
        current_color = self.color_selector.get_color()
        color_result = colorchooser.askcolor(initialcolor=current_color)
        
        if color_result and color_result[1]:
            self.color_selector.set_color(color_result[1])
    
    def add_rule(self):
        """Add new pattern rule"""
        pattern = self.pattern_entry.get().strip()
        replacement = self.replace_entry.get().strip()
        
        if pattern and replacement:
            rule = SimplePatternRule(
                pattern_template=pattern,
                replacement=replacement,
                priority=self.priority_var.get(),
                location_enabled=self.location_enabled_var.get(),
                selected_part_index=0,  # Default to first wildcard
                color=self.color_selector.get_color()
            )
            
            self.pattern_rules.append(rule)
            self.update_rules_display()
            
            # Clear inputs
            self.pattern_entry.delete(0, tk.END)
            self.pattern_entry.insert(0, "## ?? ##")
            self.replace_entry.delete(0, tk.END)
            self.priority_var.set(0)
            self.location_enabled_var.set(False)
            
            self.update_callback()
        else:
            messagebox.showwarning("Warning", "Both pattern and replacement must be provided")
    
    def update_rules_display(self):
        """Update visual display of all rules"""
        # Clear existing widgets
        for widget in self.rules_list_frame.winfo_children():
            widget.destroy()
        
        if not self.pattern_rules:
            tb.Label(self.rules_list_frame, text="No rules defined").pack()
            self.on_frame_configure(None)
            return
        
        for idx, rule in enumerate(self.pattern_rules):
            rule_frame = tb.Frame(self.rules_list_frame)
            rule_frame.pack(fill=tk.X, padx=5, pady=2)
            
            # Rule header with priority and location status
            header_frame = tb.Frame(rule_frame)
            header_frame.pack(fill=tk.X)
            
            tb.Label(header_frame, text=f"{idx+1}.", width=3).pack(side=tk.LEFT, padx=5)
            
            priority_label = tb.Label(header_frame, text=f"P:{rule.priority}", 
                                    background="#6c757d" if rule.priority == 0 else 
                                    ("#dc3545" if rule.priority < 0 else "#28a745"),
                                    foreground="white", width=4)
            priority_label.pack(side=tk.LEFT, padx=2)
            
            if rule.location_enabled:
                loc_label = tb.Label(header_frame, text="LOC", background="#007bff", 
                                   foreground="white", width=4)
                loc_label.pack(side=tk.LEFT, padx=2)
            
            # Pattern and replacement display
            content_frame = tb.Frame(rule_frame)
            content_frame.pack(fill=tk.X, pady=2)
            
            tb.Label(content_frame, text=f"Pattern: {rule.pattern_template}", 
                    width=25, anchor="w").pack(side=tk.LEFT, padx=5)
            tb.Label(content_frame, text=f"→ {rule.replacement}", 
                    width=30, anchor="w").pack(side=tk.LEFT, padx=5)
            
            # Color square and action buttons
            action_frame = tb.Frame(rule_frame)
            action_frame.pack(fill=tk.X, pady=2)
            
            def make_color_command(rule_idx):
                return lambda: self.edit_color(rule_idx)
            
            color_square = ColorSquare(action_frame, color=rule.color, command=make_color_command(idx))
            color_square.pack(side=tk.LEFT, padx=5)
            
            # Location part selector (if enabled and has wildcards)
            if rule.location_enabled and rule.get_wildcard_count() > 0:
                loc_frame = tb.Frame(action_frame)
                loc_frame.pack(side=tk.LEFT, padx=10)
                
                tb.Label(loc_frame, text="Location part:", font=("TkDefaultFont", 8)).pack()
                
                parts_frame = tb.Frame(loc_frame)
                parts_frame.pack()
                
                parts = rule.pattern_template.split()
                wildcard_idx = 0
                
                for part_idx, part in enumerate(parts):
                    if part == "##":
                        def make_part_command(rule_idx, wc_idx):
                            return lambda: self.select_location_part(rule_idx, wc_idx)
                        
                        is_selected = wildcard_idx == rule.selected_part_index
                        part_btn = tb.Button(parts_frame, text=f"##{wildcard_idx+1}", 
                                           command=make_part_command(idx, wildcard_idx),
                                           bootstyle="primary" if is_selected else "secondary",
                                           width=4)
                        part_btn.pack(side=tk.LEFT, padx=1)
                        wildcard_idx += 1
                    else:
                        tb.Label(parts_frame, text=part, font=("Courier", 8)).pack(side=tk.LEFT, padx=2)
            
            # Edit and delete buttons
            tb.Button(action_frame, text="Edit", command=lambda i=idx: self.edit_rule(i)).pack(side=tk.RIGHT, padx=2)
            tb.Button(action_frame, text="X", command=lambda i=idx: self.delete_rule(i)).pack(side=tk.RIGHT, padx=2)
            
            # Add separator
            tb.Separator(rule_frame, orient="horizontal").pack(fill=tk.X, pady=2)
        
        self.on_frame_configure(None)
    
    def select_location_part(self, rule_idx, wildcard_idx):
        """Select which wildcard part is used for location rules"""
        if rule_idx < len(self.pattern_rules):
            self.pattern_rules[rule_idx].selected_part_index = wildcard_idx
            self.update_rules_display()
            self.update_callback()
    
    def edit_color(self, idx):
        """Edit color for a rule"""
        if idx < len(self.pattern_rules):
            current_color = self.pattern_rules[idx].color
            color_result = colorchooser.askcolor(initialcolor=current_color)
            
            if color_result and color_result[1]:
                self.pattern_rules[idx].color = color_result[1]
                self.update_rules_display()
                self.update_callback()
    
    def edit_rule(self, idx):
        """Edit an existing rule"""
        if idx >= len(self.pattern_rules):
            return
            
        rule = self.pattern_rules[idx]
        
        edit_dialog = tb.Toplevel(self)
        edit_dialog.title("Edit Pattern Rule")
        edit_dialog.geometry("500x200")
        edit_dialog.resizable(False, False)
        edit_dialog.transient(self)
        edit_dialog.grab_set()
        
        tb.Label(edit_dialog, text="Pattern:").grid(row=0, column=0, padx=10, pady=10, sticky="w")
        pattern_entry = tb.Entry(edit_dialog, width=20)
        pattern_entry.grid(row=0, column=1, padx=10, pady=10)
        pattern_entry.insert(0, rule.pattern_template)
        
        tb.Label(edit_dialog, text="Replace:").grid(row=1, column=0, padx=10, pady=10, sticky="w")
        replace_entry = tb.Entry(edit_dialog, width=30)
        replace_entry.grid(row=1, column=1, padx=10, pady=10)
        replace_entry.insert(0, rule.replacement)
        
        tb.Label(edit_dialog, text="Priority:").grid(row=2, column=0, padx=10, pady=10, sticky="w")
        priority_var = tk.IntVar(value=rule.priority)
        priority_spinbox = tb.Spinbox(edit_dialog, from_=-10, to=10, width=10, textvariable=priority_var)
        priority_spinbox.grid(row=2, column=1, padx=10, pady=10, sticky="w")
        
        location_var = tk.BooleanVar(value=rule.location_enabled)
        tb.Checkbutton(edit_dialog, text="Enable Location", variable=location_var).grid(row=3, column=0, columnspan=2, pady=10)
        
        def save_changes():
            new_pattern = pattern_entry.get().strip()
            new_replacement = replace_entry.get().strip()
            
            if new_pattern and new_replacement:
                rule.pattern_template = new_pattern
                rule.replacement = new_replacement
                rule.priority = priority_var.get()
                rule.location_enabled = location_var.get()
                
                # Reset selected part if pattern changed
                if rule.get_wildcard_count() <= rule.selected_part_index:
                    rule.selected_part_index = 0
                
                self.update_rules_display()
                edit_dialog.destroy()
                self.update_callback()
            else:
                messagebox.showwarning("Warning", "Both pattern and replacement must be provided")
        
        tb.Button(edit_dialog, text="Save", command=save_changes).grid(row=4, column=0, columnspan=2, pady=10)
    
    def delete_rule(self, idx):
        """Delete a rule"""
        if idx < len(self.pattern_rules):
            del self.pattern_rules[idx]
            self.update_rules_display()
            self.update_callback()
    
    def save_rules(self):
        """Save rules to JSON file"""
        if not self.pattern_rules:
            messagebox.showwarning("Warning", "No rules to save")
            return
            
        initial_dir = HexManipulator.app_settings.get('rules_dir', os.path.expanduser('~'))
        
        file_path = filedialog.asksaveasfilename(
            title="Save Pattern Rules",
            defaultextension=".json",
            filetypes=[("JSON Files", "*.json"), ("All Files", "*.*")],
            initialdir=initial_dir
        )
        
        if file_path:
            try:
                HexManipulator.app_settings['rules_dir'] = os.path.dirname(file_path)
                HexManipulator.save_settings()
                
                rules_data = [rule.to_dict() for rule in self.pattern_rules]
                
                with open(file_path, 'w') as file:
                    json.dump(rules_data, file, indent=2)
                messagebox.showinfo("Save Successful", f"Rules saved to {os.path.basename(file_path)}")
            except Exception as e:
                messagebox.showerror("Save Error", f"Error saving rules: {str(e)}")
    
    def load_rules(self):
        """Load rules from JSON file"""
        initial_dir = HexManipulator.app_settings.get('rules_dir', os.path.expanduser('~'))
        
        file_path = filedialog.askopenfilename(
            title="Load Pattern Rules",
            filetypes=[("JSON Files", "*.json"), ("All Files", "*.*")],
            initialdir=initial_dir
        )
        
        if file_path:
            try:
                HexManipulator.app_settings['rules_dir'] = os.path.dirname(file_path)
                HexManipulator.save_settings()
                
                with open(file_path, 'r') as file:
                    data = json.load(file)
                
                self.pattern_rules = []
                
                if isinstance(data, list):
                    for rule_data in data:
                        if isinstance(rule_data, dict):
                            # Handle both old and new format
                            if "pattern_template" in rule_data:
                                # New format
                                rule = SimplePatternRule.from_dict(rule_data)
                            else:
                                # Old format - convert
                                rule = SimplePatternRule(
                                    pattern_template=rule_data.get("pattern", ""),
                                    replacement=rule_data.get("replacement", ""),
                                    priority=0,
                                    location_enabled=False,
                                    selected_part_index=0,
                                    color=rule_data.get("color", self.DEFAULT_COLOR)
                                )
                            self.pattern_rules.append(rule)
                
                self.update_rules_display()
                self.update_callback()
                messagebox.showinfo("Load Successful", f"Rules loaded from {os.path.basename(file_path)}")
            except Exception as e:
                messagebox.showerror("Load Error", f"Error loading rules: {str(e)}")
    
    def get_rules(self):
        return self.pattern_rules


class LocationRulesFrame(tb.LabelFrame):
    """Frame for location-specific replacement rules"""
    def __init__(self, parent, update_callback):
        super().__init__(parent, text="Location Rules")
        self.update_callback = update_callback
        self.location_rules = []  # List of (find, replace) tuples
        
        # Two-section layout
        main_container = tb.Frame(self)
        main_container.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Left section: Affected patterns
        left_frame = tb.LabelFrame(main_container, text="Affected Patterns")
        left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 5))
        
        self.affected_patterns_frame = tb.Frame(left_frame)
        self.affected_patterns_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Right section: Location replacements
        right_frame = tb.LabelFrame(main_container, text="Location Replacements")
        right_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(5, 0))
        
        # Add location rule controls
        add_frame = tb.Frame(right_frame)
        add_frame.pack(fill=tk.X, padx=5, pady=5)
        
        tb.Label(add_frame, text="Find:").pack(side=tk.LEFT, padx=2)
        self.find_entry = tb.Entry(add_frame, width=8, font=("Courier", 10))
        self.find_entry.pack(side=tk.LEFT, padx=2)
        
        tb.Label(add_frame, text="→").pack(side=tk.LEFT, padx=2)
        
        tb.Label(add_frame, text="Replace:").pack(side=tk.LEFT, padx=2)
        self.replace_entry = tb.Entry(add_frame, width=12, font=("Courier", 10))
        self.replace_entry.pack(side=tk.LEFT, padx=2)
        
        tb.Button(add_frame, text="Add", command=self.add_location_rule).pack(side=tk.LEFT, padx=5)
        
        # Scrollable location rules list
        rules_container = tb.Frame(right_frame)
        rules_container.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        self.rules_scrollbar = tb.Scrollbar(rules_container)
        self.rules_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.rules_canvas = tk.Canvas(rules_container)
        self.rules_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        self.rules_scrollbar.config(command=self.rules_canvas.yview)
        self.rules_canvas.config(yscrollcommand=self.rules_scrollbar.set)
        
        self.location_rules_frame = tb.Frame(self.rules_canvas)
        self.rules_canvas_window = self.rules_canvas.create_window((0, 0), window=self.location_rules_frame, anchor="nw")
        
        self.location_rules_frame.bind("<Configure>", self.on_rules_frame_configure)
        self.rules_canvas.bind("<Configure>", self.on_rules_canvas_configure)
        
        # Initial display
        self.update_affected_patterns([])
        self.update_location_rules_display()
    
    def on_rules_frame_configure(self, event):
        self.rules_canvas.configure(scrollregion=self.rules_canvas.bbox("all"))
    
    def on_rules_canvas_configure(self, event):
        self.rules_canvas.itemconfig(self.rules_canvas_window, width=event.width)
    
    def update_affected_patterns(self, pattern_rules):
        """Update display of patterns that contribute to location processing"""
        # Clear existing widgets
        for widget in self.affected_patterns_frame.winfo_children():
            widget.destroy()
        
        location_enabled_rules = [rule for rule in pattern_rules if rule.location_enabled]
        
        if not location_enabled_rules:
            tb.Label(self.affected_patterns_frame, 
                    text="No patterns enabled for location processing", 
                    foreground="#6c757d", font=("TkDefaultFont", 9, "italic")).pack(pady=20)
            return
        
        for rule in location_enabled_rules:
            pattern_frame = tb.Frame(self.affected_patterns_frame)
            pattern_frame.pack(fill=tk.X, padx=5, pady=5)
            
            # Pattern display with highlighted selected part
            pattern_display_frame = tb.Frame(pattern_frame)
            pattern_display_frame.pack(fill=tk.X, pady=2)
            
            tb.Label(pattern_display_frame, text="Pattern:", font=("TkDefaultFont", 9)).pack(side=tk.LEFT)
            
            parts = rule.pattern_template.split()
            wildcard_idx = 0
            
            for part in parts:
                if part == "##":
                    is_selected = wildcard_idx == rule.selected_part_index
                    part_label = tb.Label(pattern_display_frame, text=part,
                                        background="#007bff" if is_selected else "#e9ecef",
                                        foreground="white" if is_selected else "#495057",
                                        font=("Courier", 9, "bold"), relief="raised", bd=1)
                    part_label.pack(side=tk.LEFT, padx=1)
                    wildcard_idx += 1
                else:
                    tb.Label(pattern_display_frame, text=part, 
                           font=("Courier", 9), foreground="#495057").pack(side=tk.LEFT, padx=1)
            
            # Show which part is selected
            selected_text = f"Selected: #{rule.selected_part_index + 1} wildcard"
            tb.Label(pattern_frame, text=selected_text, 
                   font=("TkDefaultFont", 8), foreground="#007bff").pack(anchor="w")
            
            # Add separator
            tb.Separator(pattern_frame, orient="horizontal").pack(fill=tk.X, pady=2)
    
    def add_location_rule(self):
        """Add new location replacement rule"""
        find_text = self.find_entry.get().strip()
        replace_text = self.replace_entry.get().strip()
        
        if find_text and replace_text:
            self.location_rules.append((find_text, replace_text))
            self.update_location_rules_display()
            
            # Clear inputs
            self.find_entry.delete(0, tk.END)
            self.replace_entry.delete(0, tk.END)
            
            self.update_callback()
        else:
            messagebox.showwarning("Warning", "Both find and replace text must be provided")
    
    def update_location_rules_display(self):
        """Update display of location replacement rules"""
        # Clear existing widgets
        for widget in self.location_rules_frame.winfo_children():
            widget.destroy()
        
        if not self.location_rules:
            tb.Label(self.location_rules_frame, text="No location rules defined", 
                   foreground="#6c757d", font=("TkDefaultFont", 9, "italic")).pack(pady=10)
            self.on_rules_frame_configure(None)
            return
        
        for idx, (find_text, replace_text) in enumerate(self.location_rules):
            rule_frame = tb.Frame(self.location_rules_frame)
            rule_frame.pack(fill=tk.X, padx=5, pady=2)
            
            # Rule display
            content_frame = tb.Frame(rule_frame)
            content_frame.pack(fill=tk.X)
            
            tb.Label(content_frame, text=f"{idx+1}.", width=3).pack(side=tk.LEFT, padx=2)
            
            find_label = tb.Label(content_frame, text=find_text, 
                                background="#f8f9fa", font=("Courier", 9), 
                                relief="sunken", bd=1, width=8)
            find_label.pack(side=tk.LEFT, padx=2)
            
            tb.Label(content_frame, text="→").pack(side=tk.LEFT, padx=2)
            
            replace_label = tb.Label(content_frame, text=replace_text, 
                                   background="#e3f2fd", font=("Courier", 9), 
                                   relief="sunken", bd=1, width=12)
            replace_label.pack(side=tk.LEFT, padx=2)
            
            # Action buttons
            tb.Button(content_frame, text="Edit", 
                     command=lambda i=idx: self.edit_location_rule(i)).pack(side=tk.RIGHT, padx=2)
            tb.Button(content_frame, text="X", 
                     command=lambda i=idx: self.delete_location_rule(i)).pack(side=tk.RIGHT, padx=2)
            
            # Add separator
            tb.Separator(rule_frame, orient="horizontal").pack(fill=tk.X, pady=1)
        
        self.on_rules_frame_configure(None)
    
    def edit_location_rule(self, idx):
        """Edit an existing location rule"""
        if idx >= len(self.location_rules):
            return
            
        find_text, replace_text = self.location_rules[idx]
        
        edit_dialog = tb.Toplevel(self)
        edit_dialog.title("Edit Location Rule")
        edit_dialog.geometry("300x150")
        edit_dialog.resizable(False, False)
        edit_dialog.transient(self)
        edit_dialog.grab_set()
        
        tb.Label(edit_dialog, text="Find:").grid(row=0, column=0, padx=10, pady=10, sticky="w")
        find_entry = tb.Entry(edit_dialog, width=15, font=("Courier", 10))
        find_entry.grid(row=0, column=1, padx=10, pady=10)
        find_entry.insert(0, find_text)
        
        tb.Label(edit_dialog, text="Replace:").grid(row=1, column=0, padx=10, pady=10, sticky="w")
        replace_entry = tb.Entry(edit_dialog, width=15, font=("Courier", 10))
        replace_entry.grid(row=1, column=1, padx=10, pady=10)
        replace_entry.insert(0, replace_text)
        
        def save_changes():
            new_find = find_entry.get().strip()
            new_replace = replace_entry.get().strip()
            
            if new_find and new_replace:
                self.location_rules[idx] = (new_find, new_replace)
                self.update_location_rules_display()
                edit_dialog.destroy()
                self.update_callback()
            else:
                messagebox.showwarning("Warning", "Both find and replace text must be provided")
        
        tb.Button(edit_dialog, text="Save", command=save_changes).grid(row=2, column=0, columnspan=2, pady=10)
    
    def delete_location_rule(self, idx):
        """Delete a location rule"""
        if idx < len(self.location_rules):
            del self.location_rules[idx]
            self.update_location_rules_display()
            self.update_callback()
    
    def get_rules(self):
        return self.location_rules


class OutputFrame(tb.LabelFrame):
    """Frame for displaying transformed output"""
    def __init__(self, parent, title="Output"):
        super().__init__(parent, text=title)
        self.DEFAULT_COLOR = "#cc7000"
        
        self.text_output = scrolledtext.ScrolledText(self, height=6, wrap=tk.WORD)
        self.text_output.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        self.text_output.config(state=tk.DISABLED)
    
    def set_output(self, text, pattern_rules=None):
        """Set output text with optional highlighting"""
        self.text_output.config(state=tk.NORMAL)
        self.text_output.delete("1.0", tk.END)
        self.text_output.insert("1.0", text)
        
        # Remove existing highlight tags
        for tag in self.text_output.tag_names():
            if tag.startswith("output_color_"):
                self.text_output.tag_remove(tag, "1.0", tk.END)
        
        if pattern_rules:
            for i, rule in enumerate(pattern_rules):
                try:
                    # Highlight replacement text with rule's color
                    replacement_text = rule.replacement
                    
                    # Skip highlighting if replacement contains escape sequences or complex templates
                    if any(seq in replacement_text for seq in ['\\n', '\\t', '\\r', '{', '}']):
                        continue
                    
                    tag_name = f"output_color_{i}"
                    if tag_name not in self.text_output.tag_names():
                        self.text_output.tag_configure(tag_name, background=rule.color, 
                                                     foreground="white", font=("TkDefaultFont", 10, "bold"))
                    else:
                        self.text_output.tag_configure(tag_name, background=rule.color)
                    
                    self.highlight_text(replacement_text, tag_name)
                except:
                    continue
        
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


class EnhancedHexProcessor:
    """Process hex data with pattern and location rules"""
    
    def process_hex_data(self, input_data, pattern_rules, location_rules):
        """Apply two-stage processing: patterns first, then locations"""
        # Sort pattern rules by priority (negative first, then by order)
        sorted_patterns = sorted(pattern_rules, key=lambda r: (r.priority, pattern_rules.index(r)))
        
        # Stage 1: Apply pattern rules
        intermediate_result = self.apply_pattern_rules(input_data, sorted_patterns)
        
        # Stage 2: Apply location rules (only to location-enabled patterns)
        final_result = self.apply_location_rules(intermediate_result, pattern_rules, location_rules)
        
        return intermediate_result, final_result
    
    def apply_pattern_rules(self, text, pattern_rules):
        """Apply pattern rules with template processing"""
        result = text
        
        for rule in pattern_rules:
            try:
                regex_pattern = rule.to_regex()
                
                def replace_func(match):
                    return rule.process_replacement(match.groups())
                
                result = re.sub(regex_pattern, replace_func, result)
            except re.error:
                # Skip invalid regex patterns
                continue
        
        return result
    
    def apply_location_rules(self, text, pattern_rules, location_rules):
        """Apply location rules only to specified parts of location-enabled patterns"""
        if not location_rules:
            return text
        
        result = text
        
        # Get location-enabled patterns and their capture groups
        location_patterns = [rule for rule in pattern_rules if rule.location_enabled]
        
        if not location_patterns:
            return text
        
        # For simplicity, apply location rules to remaining text
        # In a more sophisticated implementation, we would track which parts
        # of the text came from which capture groups and only replace those
        for find_text, replace_text in location_rules:
            if find_text and replace_text:
                # Use word boundaries to avoid partial matches
                pattern = r'\b' + re.escape(find_text) + r'\b'
                result = re.sub(pattern, replace_text, result)
        
        return result


class HexManipulator(tb.Window):
    """Enhanced main application window"""
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
        self.title("Enhanced Hex Data Manipulator")
        
        # Apply saved window state or default to maximized
        if self.app_settings.get('window_is_maximized', True):
            self.state('zoomed')  # Windows maximized state
        elif self.app_settings.get('window_geometry'):
            try:
                self.geometry(self.app_settings['window_geometry'])
            except:
                self.geometry('1200x800')
        else:
            self.geometry('1200x800')
        
        self.processor = EnhancedHexProcessor()
        self.create_ui()
        
        # Save settings when closing
        self.protocol("WM_DELETE_WINDOW", self.on_closing)
    
    def create_ui(self):
        """Create the enhanced application UI"""
        main_frame = tb.Frame(self)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Create resizable paned window with more sections
        self.paned_window = tk.PanedWindow(main_frame, orient=tk.VERTICAL)
        self.paned_window.pack(fill=tk.BOTH, expand=True)
        
        # Input frame
        self.input_frame = InputFrame(self.paned_window, self.update_output)
        self.paned_window.add(self.input_frame, stretch="always", minsize=120)
        
        # Pattern rules frame
        self.pattern_rules_frame = PatternRulesFrame(self.paned_window, self.update_output)
        self.paned_window.add(self.pattern_rules_frame, stretch="always", minsize=200)
        
        # Location rules frame
        self.location_rules_frame = LocationRulesFrame(self.paned_window, self.update_output)
        self.paned_window.add(self.location_rules_frame, stretch="always", minsize=150)
        
        # Intermediate output frame
        self.intermediate_output_frame = OutputFrame(self.paned_window, "Intermediate Output (After Patterns)")
        self.paned_window.add(self.intermediate_output_frame, stretch="always", minsize=100)
        
        # Final output frame
        self.final_output_frame = OutputFrame(self.paned_window, "Final Output (After Locations)")
        self.paned_window.add(self.final_output_frame, stretch="always", minsize=100)
        
        # Restore pane positions if available
        if self.app_settings.get('pane_positions') and len(self.app_settings['pane_positions']) >= 4:
            try:
                positions = self.app_settings['pane_positions']
                self.update_idletasks()
                for i, pos in enumerate(positions[:4]):  # Only use first 4 positions
                    self.paned_window.sash_place(i, 0, pos)
            except Exception as e:
                print(f"Error restoring pane positions: {str(e)}")
    
    def update_output(self):
        """Process input and update all outputs when changes occur"""
        input_text = self.input_frame.get_input()
        pattern_rules = self.pattern_rules_frame.get_rules()
        location_rules = self.location_rules_frame.get_rules()
        
        # Update location rules display with current pattern rules
        self.location_rules_frame.update_affected_patterns(pattern_rules)
        
        # Highlight patterns in input
        if pattern_rules:
            self.input_frame.highlight_patterns(pattern_rules)
        
        if input_text:
            # Process with two-stage pipeline
            intermediate_result, final_result = self.processor.process_hex_data(
                input_text, pattern_rules, location_rules)
            
            # Update both output frames
            self.intermediate_output_frame.set_output(intermediate_result, pattern_rules)
            self.final_output_frame.set_output(final_result, pattern_rules)
        else:
            # Clear outputs
            self.intermediate_output_frame.set_output("", None)
            self.final_output_frame.set_output("", None)
    
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