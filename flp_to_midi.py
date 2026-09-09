import argparse,json,struct,subprocess,sys
from pathlib import Path

NOTE_EVENT=224
NOTE_SIZE=24
MAX_NOTES_PER_MIDI_FILE=30000


def read_varint(data,pos,end):
    value=0; shift=0
    while pos<end and shift<70:
        byte=data[pos]; pos+=1; value|=(byte&127)<<shift
        if not byte&128: return value,pos
        shift+=7
    raise ValueError('invalid FL Studio event length')

def load_native(path):
    data=path.read_bytes()
    if len(data)<22 or data[:4]!=b'FLhd': raise ValueError('not a native FL Studio binary file')
    header_length=struct.unpack_from('<I',data,4)[0]
    if header_length<6 or 8+header_length+8>len(data): raise ValueError('invalid FL Studio header')
    ppq=struct.unpack_from('<H',data,12)[0]; chunk=8+header_length
    if data[chunk:chunk+4]!=b'FLdt': raise ValueError('FL Studio data chunk is missing')
    length=struct.unpack_from('<I',data,chunk+4)[0]; start=chunk+8; end=start+length
    if end>len(data): raise ValueError('FL Studio data chunk is truncated')
    patterns={}; current_pattern=None; pos=start
    while pos<end:
        event_id=data[pos]; pos+=1
        if event_id<64: size=1
        elif event_id<128: size=2
        elif event_id<192: size=4
        else: size,pos=read_varint(data,pos,end)
        payload=data[pos:pos+size]
        if len(payload)!=size: raise ValueError('truncated FL Studio event')
        if event_id==65 and size>=2: current_pattern=struct.unpack_from('<H',payload)[0]
        elif event_id==NOTE_EVENT and current_pattern is not None:
            notes=patterns.setdefault(current_pattern,[])
            if size%NOTE_SIZE: raise ValueError('malformed native note event')
            for offset in range(0,size,NOTE_SIZE):
                record=payload[offset:offset+NOTE_SIZE]
                start_tick=struct.unpack_from('<I',record,0)[0]; duration=struct.unpack_from('<I',record,8)[0]
                pitch=struct.unpack_from('<H',record,12)[0]; channel=record[19]&15; velocity=max(1,min(127,round(record[21]*127/128)))
                if pitch<=127: notes.append({'start':start_tick,'duration':max(1,duration),'note':pitch,'velocity':velocity,'channel':channel})
        pos+=size
    tracks=[]
    for pattern_id,notes in sorted(patterns.items()):
        if notes:
            tracks.append({'channel':notes[0].get('channel',0),'notes':notes,'name':f'Pattern {pattern_id}'})
    if not tracks: raise ValueError('no piano-roll notes were found')
    return {'tempo':120.0,'ppq':ppq,'tracks':tracks}

def load(path):
    raw=path.read_bytes()
    if raw[:4]==b'FLhd': return load_native(path)
    try: text=raw.decode('utf-8')
    except UnicodeDecodeError:
        try: text=raw.decode('cp932')
        except UnicodeDecodeError as error: raise ValueError('not JSON or a recognized native FL Studio file') from error
    try: data=json.loads(text)
    except json.JSONDecodeError as error: raise ValueError('not converter JSON or a recognized native FL Studio file') from error
    if not isinstance(data,dict) or not isinstance(data.get('tracks'),list): raise ValueError('project must contain a tracks array')
    return data

def varlen(value):
    output=[value&127]; value>>=7
    while value: output.append((value&127)|128); value>>=7
    output.reverse()
    for index in range(len(output)-1): output[index]|=128
    return bytes(output)

def write_midi(project, output, max_notes_per_track=None):
    ppq=int(project.get('ppq',480)); tempo=float(project.get('tempo',120)); micros=max(1,int(60000000/tempo))
    tracks=[]; tempo_track=bytes([0,255,81,3,(micros>>16)&255,(micros>>8)&255,micros&255,0,255,47,0]); tracks.append(tempo_track)
    for source in project['tracks']:
        notes=source.get('notes',[])
        chunks=[notes] if max_notes_per_track is None else [notes[index:index+max_notes_per_track] for index in range(0,len(notes),max_notes_per_track)]
        for chunk in chunks:
            events=[]
            for note in chunk:
                channel=int(note.get('channel',source.get('channel',0)))&15; start=int(note['start']); end=start+max(1,int(note['duration'])); pitch=max(0,min(127,int(note['note']))); velocity=int(note.get('velocity',100)); events.extend([(start,1,channel,pitch,velocity),(end,0,channel,pitch,0)])
            events.sort(key=lambda event:(event[0],event[1])); body=bytearray(); cursor=0
            for time,is_on,channel,pitch,velocity in events:
                body.extend(varlen(time-cursor)); body.extend([0x90|channel if is_on else 0x80|channel,pitch,velocity]); cursor=time
            body.extend([0,255,47,0]); tracks.append(bytes(body))
    file=bytearray(b'MThd'+struct.pack('>IHHH',6,1,len(tracks),ppq))
    for track in tracks: file.extend(b'MTrk'+struct.pack('>I',len(track))+track)
    output.parent.mkdir(parents=True,exist_ok=True); output.write_bytes(file)
def write_midi_files(project, output, max_notes_per_file=MAX_NOTES_PER_MIDI_FILE):
    all_notes=[(track_index,note) for track_index,track in enumerate(project['tracks']) for note in track.get('notes',[])]
    if len(all_notes)<=max_notes_per_file:
        write_midi(project,output)
        return [output]
    outputs=[]
    for batch_index in range(0,len(all_notes),max_notes_per_file):
        grouped=[{'channel':track.get('channel',0),'notes':[]} for track in project['tracks']]
        for track_index,note in all_notes[batch_index:batch_index+max_notes_per_file]: grouped[track_index]['notes'].append(note)
        batch_output=output.with_name(f'{output.stem}.part{batch_index//max_notes_per_file+1:03d}{output.suffix}')
        write_midi({'tempo':project.get('tempo',120),'ppq':project.get('ppq',480),'tracks':grouped},batch_output)
        outputs.append(batch_output)
    return outputs

def convert_file(input_path,output_path,writer=None,max_notes_per_track=None):
    project=load(input_path)
    if writer and writer.is_file():
        result=subprocess.run([str(writer),'--output',str(output_path)],input=json.dumps(project),text=True,capture_output=True)
        if result.returncode==0: return result.stdout.strip() or f'Wrote {output_path}'
    total=sum(len(track.get('notes',[])) for track in project['tracks'])
    if max_notes_per_track is None:
        write_midi(project,output_path)
        return f'Wrote {total} notes to {output_path} (Python fallback, unlimited mode)'
    outputs=write_midi_files(project,output_path,max_notes_per_track)
    if len(outputs)==1: return f'Wrote {total} notes to {outputs[0]} (Python fallback)'
    return f'Wrote {total} notes to {len(outputs)} MIDI files: {outputs[0].name} through {outputs[-1].name}'
def main():
    parser=argparse.ArgumentParser(description='Convert native FL Studio FSC/FLP files to MIDI'); parser.add_argument('input',type=Path); parser.add_argument('--output',type=Path,required=True); parser.add_argument('--midi-writer',type=Path,default=None,help='optional Rust writer; Python is used by default'); args=parser.parse_args()
    try: print(convert_file(args.input,args.output,args.midi_writer))
    except (OSError,ValueError,RuntimeError) as error: print(f'error: {error}',file=sys.stderr); return 1
    return 0
if __name__=='__main__': raise SystemExit(main())








