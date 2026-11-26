"""One model request per chat turn; no OpenCode server or agent delegation."""
import json, re, shlex, time
from functools import lru_cache
from pathlib import Path
import httpx
from pydantic import ValidationError
from .schemas import ModelReply, Proposal
from .store import Fault

ROOT=Path(__file__).resolve().parents[1]
class Planner:
    def __init__(self, key='', model='deepseek-flash', client=None, provider='deepseek'):
        self.provider = provider
        self.endpoint = {
            'deepseek': 'https://api.deepseek.com/chat/completions',
            'openrouter': 'https://openrouter.ai/api/v1/chat/completions',
        }[provider]
        self.key=key; self.model=model
        self.client=client or httpx.Client(timeout=httpx.Timeout(30,connect=5),trust_env=False,follow_redirects=False)
        self.context={p.stem:p.read_text() for p in (ROOT/'.opencode/context').glob('*.md')}
        self.agents={p.stem:re.sub(r'\A---\n.*?\n---\n','',p.read_text(),count=1,flags=re.S) for p in (ROOT/'.opencode/agents').glob('*.md')}
        required={'navigation','security-policy','routing-rules','approval-policy','verification-rules','file-management','cryptography','vault-management','linux-operations'}
        if not required<=self.context.keys() or not {'ciphermate','file-agent','crypto-agent','vault-agent','linux-agent','context-scout'}<=self.agents.keys(): raise RuntimeError('Missing MVP Markdown files')
    def prompt(self,caps):
        return self._prompt(json.dumps(caps,separators=(',',':'),sort_keys=True))
    @lru_cache(maxsize=4)
    def _prompt(self,registry_json):
        # Small static knowledge base; cached by provider when possible. All four domain modules
        # are read locally once to avoid a separate routing LLM call and missed cross-domain intents.
        return ('You are CipherMate, a single conversational model. The following Markdown profiles '
                'are domain instruction references, not separate agents. Do not delegate or read files. '
                'The private Python adapter is the sole execution authority. The Markdown describes an earlier proposal-only harness: '
                'ignore its OpenCode delegation and read-tool instructions, preserve its safety rules. '
                'The actual enabled registry below supersedes all target capability lists. Never invent execution, results, identity, or approval. '
                'Return one JSON object: {"decision":"answer|clarify|reject|unsupported|propose","message":"short response","proposal":null}. '
                'For propose use proposal={"schema_version":"1.0","agent":"domain ID from registry","decision":"propose",'
                '"operation":"registered operation","parameters":{},"reason":"safe description","postconditions":[],"approval_hint":"unknown"}. '
                'One exact operation per turn; ask for missing data. For multi-step requests explain dependencies and start only the first exact task when appropriate. '
                'Never ask for secret values in chat. Private vault entry is through the separate UI. Never echo raw secrets. '
                'Do not invent filenames or labels. Uploaded file bytes and vault values are never provided to you. '
                'Use only these capabilities: '+registry_json+'\n\n'
                +'\n\n'.join(self.agents[n] for n in ('ciphermate','file-agent','crypto-agent','vault-agent','linux-agent'))
                +'\n\n'+'\n\n'.join(self.context[n] for n in sorted(self.context)))
    def plan(self,message,caps):
        if not self.key: return self.offline(message,caps)
        payload={'model':self.model,'messages':[{'role':'system','content':self.prompt(caps)},{'role':'user','content':message}],
                 'response_format':{'type':'json_object'},'max_tokens':1300,'stream':False}
        if self.provider == 'deepseek':
            payload['thinking'] = {'type': 'disabled'}
        for attempt in range(2):
            try:
                r=self.client.post(self.endpoint,json=payload,headers={'Authorization':'Bearer '+self.key})
                if r.status_code in (429,502,503,504) and attempt==0: time.sleep(.5); continue
                r.raise_for_status()
                content=r.json()['choices'][0]['message']['content']
                reply=ModelReply.model_validate_json(content)
                if (reply.decision=='propose') != (reply.proposal is not None): raise ValueError()
                return reply
            except (httpx.TimeoutException,httpx.ConnectError):
                if attempt==0: time.sleep(.5); continue
                raise Fault('MODEL_UNAVAILABLE',503)
            except (ValidationError,ValueError,KeyError,IndexError,TypeError):
                if attempt==0: continue
                raise Fault('INVALID_MODEL_OUTPUT',502)
            except httpx.HTTPError: raise Fault('MODEL_UNAVAILABLE',503)
        raise Fault('MODEL_UNAVAILABLE',503)
    @staticmethod
    def offline(message,caps):
        # Deterministic smoke-test mode; no claims of general language understanding.
        try: w=shlex.split(message)
        except ValueError: w=[]
        op=None; p={}
        if w in (['list'],['list','files']): op='file.list'
        elif w==['duplicates']: op='file.duplicates'
        elif w==['vault','list']: op='vault.list'
        elif len(w)==2 and w[0] in ('hash','inspect','identify','delete'):
            op={'hash':'crypto.hash','inspect':'file.inspect','identify':'crypto.identify_format','delete':'file.delete'}[w[0]]; p={'source':w[1]}
        elif len(w)==4 and w[0] in ('copy','move','rename') and w[2]=='to':
            op='file.'+w[0]; p={'source':w[1],'destination':w[3]}
        elif len(w)==6 and w[0] in ('encrypt','decrypt','sign') and w[2]=='to' and w[4]=='using':
            op='crypto.'+w[0]; p={'source':w[1],'destination':w[3],'key_ref':w[5]}
        elif len(w)==2 and w[0]=='search': op='file.search'; p={'query':w[1]}
        elif len(w)==4 and w[0]=='create' and w[1]=='key': op='crypto.key_create'; p={'kind':w[2],'key_ref':w[3]}
        elif len(w)==4 and w[0]=='public-key' and w[2]=='to': op='crypto.public_key'; p={'key_ref':w[1],'destination':w[3]}
        elif len(w)==6 and w[0]=='verify' and w[2]=='with' and w[4]=='using': op='crypto.verify'; p={'source':w[1],'signature':w[3],'public_key':w[5]}
        elif len(w)==4 and w[0]=='compare' and w[2]=='to': op='crypto.compare'; p={'source':w[1],'expected_sha256':w[3]}
        elif len(w)==3 and w[:2]==['vault','delete']: op='vault.delete'; p={'key_ref':w[2]}
        elif w==['history','clear']: op='history.clear'
        elif w==['linux','system']: op='linux.system'
        elif w==['script','execute']: op='script.execute_template'
        elif w==['linux','resources']: op='linux.resources'
        elif w==['script','preview']: op='script.propose'
        if op in caps: return ModelReply(decision='propose',message='Offline operation proposal.',proposal=Proposal(agent=caps[op]['agent'],operation=op,parameters=p))
        return ModelReply(decision='clarify',message='Offline lab mode. Try list files, hash report.txt, duplicates, or encrypt report.txt to report.cm using lab-key. Other commands: create key fernet lab-key, create key ed25519 lab-sign-key, verify report.txt with report.sig using pub.pem. Configure OpenRouter or DeepSeek for natural language.')
