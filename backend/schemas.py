from typing import Literal, Annotated
import re
from pydantic import BaseModel, ConfigDict, Field, field_validator

class Strict(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)

Name = Annotated[str, Field(min_length=1, max_length=200)]
Label = Annotated[str, Field(pattern=r'^[A-Za-z0-9][A-Za-z0-9_.-]{0,63}$')]

def check_name(name: str) -> str:
    # Logical paths only: no operating-system path resolution.
    if not isinstance(name, str) or not 1 <= len(name) <= 200:
        raise ValueError('invalid logical name')
    if any(not re.fullmatch(r'[A-Za-z0-9_][A-Za-z0-9_. -]{0,79}', p) or p.endswith((' ', '.')) for p in name.split('/')):
        raise ValueError('invalid logical name')
    return name

class Empty(Strict): pass
class Source(Strict):
    source: Name
    @field_validator('source')
    @classmethod
    def safe(cls, v): return check_name(v)
class Pair(Source):
    destination: Name
    @field_validator('destination')
    @classmethod
    def safe_dest(cls, v): return check_name(v)
class KeyPair(Pair): key_ref: Label
class Verify(Source):
    signature: Name
    public_key: Name
    @field_validator('signature','public_key')
    @classmethod
    def safe_refs(cls, v): return check_name(v)
class Compare(Source): expected_sha256: Annotated[str, Field(pattern=r'^[a-fA-F0-9]{64}$')]
class Search(Strict): query: Annotated[str, Field(max_length=100)] = ''
class KeyCreate(Strict):
    key_ref: Label
    kind: Literal['fernet','ed25519']
class PublicKey(Strict):
    key_ref: Label
    destination: Name
    @field_validator('destination')
    @classmethod
    def safe_dest(cls, v): return check_name(v)
class VaultRef(Strict): key_ref: Label
class PrivateEntry(Strict):
    key_ref: Label
    kind: Literal['credential','fernet','ed25519']
    value: Annotated[str, Field(min_length=1,max_length=8192)]
class Proposal(Strict):
    schema_version: Literal['1.0'] = '1.0'
    agent: Literal['ciphermate','file-agent','crypto-agent','vault-agent','linux-agent']
    decision: Literal['propose'] = 'propose'
    operation: Annotated[str, Field(max_length=50)]
    parameters: dict
    reason: Annotated[str, Field(max_length=500)] = ''
    postconditions: list[Annotated[str, Field(max_length=200)]] = Field(default_factory=list,max_length=8)
    approval_hint: Literal['required','not_required','unknown'] = 'unknown'
class Approval(Strict):
    approve: bool
    plan_digest: Annotated[str, Field(pattern=r'^[a-f0-9]{64}$')]
class Chat(Strict):
    message: Annotated[str, Field(min_length=1,max_length=4000)]
class ModelReply(Strict):
    decision: Literal['answer','clarify','reject','unsupported','propose']
    message: Annotated[str, Field(max_length=3000)]
    proposal: Proposal | None = None

# (parameter schema, mutation/sensitive approval required, domain)
REGISTRY = {
    'file.list': (Empty, False, 'file-agent'), 'file.search': (Search, False, 'file-agent'),
    'file.inspect': (Source, False, 'file-agent'), 'file.duplicates': (Empty, False, 'file-agent'),
    'file.copy': (Pair, True, 'file-agent'), 'file.move': (Pair, True, 'file-agent'),
    'file.rename': (Pair, True, 'file-agent'), 'file.delete': (Source, True, 'file-agent'),
    'crypto.hash': (Source, False, 'crypto-agent'), 'crypto.compare': (Compare, False, 'crypto-agent'),
    'crypto.encrypt': (KeyPair, True, 'crypto-agent'), 'crypto.decrypt': (KeyPair, True, 'crypto-agent'),
    'crypto.identify_format': (Source, False, 'crypto-agent'), 'crypto.sign': (KeyPair, True, 'crypto-agent'),
    'crypto.verify': (Verify, False, 'crypto-agent'), 'crypto.key_create': (KeyCreate, True, 'crypto-agent'),
    'crypto.public_key': (PublicKey, True, 'crypto-agent'), 'vault.list': (Empty, False, 'vault-agent'),
    'vault.delete': (VaultRef, True, 'vault-agent'), 'history.clear': (Empty, True, 'ciphermate'),
    'linux.resources': (Empty, False, 'linux-agent'), 'linux.system': (Empty, False, 'linux-agent'),
    'script.propose': (Empty, False, 'linux-agent'), 'script.execute_template': (Empty, True, 'linux-agent'),
}
