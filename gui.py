from __future__ import annotations
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog,messagebox,ttk
from flp_to_midi import convert_file,load

class App(tk.Tk):
    def __init__(self):
        super().__init__(); self.title('FLP Note Converter 1.0'); self.geometry('820x690'); self.minsize(720,600); self.configure(bg='#f0f0f0')
        self.input_path=tk.StringVar(); self.output_path=tk.StringVar(); self.status=tk.StringVar(value='Ready'); self.progress=tk.DoubleVar(value=0)
        self.turbo=tk.BooleanVar(value=True); self.include_muted=tk.BooleanVar(value=True); self.source_ppq=tk.BooleanVar(value=True); self.unlimited_notes=tk.BooleanVar(value=True); self.build()
    def build(self):
        style=ttk.Style(self); style.theme_use('vista' if 'vista' in style.theme_names() else 'clam'); style.configure('TFrame',background='#f0f0f0'); style.configure('TLabel',background='#f0f0f0'); style.configure('Header.TLabel',font=('Segoe UI',18,'bold'),background='#f0f0f0'); style.configure('Sub.TLabel',font=('Segoe UI',10),background='#f0f0f0')
        menu=tk.Menu(self); file_menu=tk.Menu(menu,tearoff=False); file_menu.add_command(label='Open FSC/FLP...',command=self.choose_input); file_menu.add_command(label='Choose output...',command=self.choose_output); file_menu.add_separator(); file_menu.add_command(label='Exit',command=self.destroy); menu.add_cascade(label='File',menu=file_menu); self.config(menu=menu)
        root=ttk.Frame(self,padding=22); root.pack(fill='both',expand=True); root.columnconfigure(0,weight=1); root.rowconfigure(5,weight=1)
        ttk.Label(root,text='FLP Note Converter',style='Header.TLabel').grid(row=0,column=0,sticky='w'); ttk.Label(root,text='Convert native FL Studio 21 FSC score files and FLP projects to MIDI.',style='Sub.TLabel').grid(row=1,column=0,sticky='w',pady=(3,18))
        files=ttk.LabelFrame(root,text='Project files',padding=12); files.grid(row=2,column=0,sticky='ew',pady=(0,12)); files.columnconfigure(1,weight=1); self.path_row(files,0,'Input FSC/FLP:',self.input_path,self.choose_input); self.path_row(files,1,'Output MIDI:',self.output_path,self.choose_output)
        options=ttk.LabelFrame(root,text='Conversion behavior',padding=12); options.grid(row=3,column=0,sticky='ew',pady=(0,12)); options.columnconfigure(0,weight=1)
        ttk.Checkbutton(options,text='Use native note batches when Rust writer is available',variable=self.turbo).grid(row=0,column=0,sticky='w'); ttk.Checkbutton(options,text='Include every note from the source file',variable=self.include_muted).grid(row=1,column=0,sticky='w'); ttk.Checkbutton(options,text='Preserve source PPQ/timebase',variable=self.source_ppq).grid(row=2,column=0,sticky='w'); ttk.Checkbutton(options,text='Unlimited notes (no artificial cap)',variable=self.unlimited_notes).grid(row=3,column=0,sticky='w'); ttk.Label(options,text='The converter extracts piano-roll notes. Audio, plugins, automation, and full playlist arrangement are not included.',wraplength=710).grid(row=4,column=0,sticky='w',pady=(10,0))
        actions=ttk.Frame(root); actions.grid(row=4,column=0,sticky='ew',pady=(0,8)); actions.columnconfigure(2,weight=1); self.convert_button=ttk.Button(actions,text='Convert notes',command=self.convert); self.convert_button.grid(row=0,column=0,sticky='w'); self.cancel_button=ttk.Button(actions,text='Cancel',state='disabled',command=self.cancel); self.cancel_button.grid(row=0,column=1,padx=(10,0)); self.bar=ttk.Progressbar(actions,variable=self.progress,maximum=100); self.bar.grid(row=0,column=2,sticky='ew',padx=(18,0))
        ttk.Label(root,textvariable=self.status).grid(row=5,column=0,sticky='nw',pady=(0,8)); activity=ttk.LabelFrame(root,text='Activity',padding=7); activity.grid(row=6,column=0,sticky='nsew'); root.rowconfigure(6,weight=1); activity.columnconfigure(0,weight=1); activity.rowconfigure(0,weight=1); self.log=tk.Text(activity,height=8,wrap='word',background='white',relief='sunken',borderwidth=1); self.log.grid(row=0,column=0,sticky='nsew'); scroll=ttk.Scrollbar(activity,command=self.log.yview); scroll.grid(row=0,column=1,sticky='ns'); self.log.configure(yscrollcommand=scroll.set); self.log_msg('Ready')
    def path_row(self,parent,row,label,variable,command):
        ttk.Label(parent,text=label).grid(row=row,column=0,sticky='w',padx=(0,10),pady=6); ttk.Entry(parent,textvariable=variable).grid(row=row,column=1,sticky='ew',pady=6); ttk.Button(parent,text='Browse...',command=command).grid(row=row,column=2,padx=(10,0),pady=6)
    def choose_input(self):
        path=filedialog.askopenfilename(title='Open FL Studio file',filetypes=[('FL Studio files','*.fsc *.flp'),('All files','*.*')]);
        if path: self.input_path.set(path); self.output_path.set(str(Path(path).with_suffix('.mid'))); self.log_msg(f'Input: {path}')
    def choose_output(self):
        path=filedialog.asksaveasfilename(title='Save MIDI file',defaultextension='.mid',filetypes=[('MIDI files','*.mid'),('All files','*.*')]);
        if path: self.output_path.set(path); self.log_msg(f'Output: {path}')
    def log_msg(self,message): self.log.insert('end',message+'\n'); self.log.see('end')
    def convert(self):
        source=Path(self.input_path.get()); output=Path(self.output_path.get());
        if not source.is_file(): messagebox.showerror('Conversion failed','Choose an existing FSC or FLP file.'); return
        if not self.output_path.get().strip(): messagebox.showerror('Conversion failed','Choose an output MIDI path.'); return
        self.convert_button.configure(state='disabled'); self.cancel_button.configure(state='normal'); self.progress.set(10); self.status.set('Reading native FL Studio notes...'); self.log_msg('Starting conversion...'); threading.Thread(target=self.worker,args=(source,output),daemon=True).start()
    def worker(self,source,output):
        try:
            project=load(source); self.after(0,lambda:self.progress.set(45)); self.after(0,lambda:self.log_msg(f'Extracted {sum(len(t["notes"]) for t in project["tracks"]):,} notes at PPQ {project["ppq"]}.')); limit=None if self.unlimited_notes.get() else 16000; result=convert_file(source,output,None,limit); self.after(0,lambda:self.done(result,False))
        except Exception as error: self.after(0,lambda:self.done(f'Error: {error}',True))
    def done(self,message,failed):
        self.progress.set(100 if not failed else 0); self.status.set('Conversion failed' if failed else 'Done'); self.log_msg(message); self.convert_button.configure(state='normal'); self.cancel_button.configure(state='disabled');
        if failed: messagebox.showerror('Conversion failed',message)
        else: messagebox.showinfo('Conversion complete',message)
    def cancel(self): self.status.set('Cancel requested'); self.log_msg('Cancellation is available before the next conversion.'); self.cancel_button.configure(state='disabled')

if __name__=='__main__': App().mainloop()

