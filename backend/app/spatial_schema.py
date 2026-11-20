"""Untrusted AI output is data only: bounded, finite, typed geometry and references."""
import math,re
from typing import Literal
from pydantic import BaseModel,ConfigDict,Field,field_validator,model_validator

class Strict(BaseModel):
    model_config=ConfigDict(extra='forbid',allow_inf_nan=False)

class Vec(Strict):
    x:float=Field(default=0,ge=-25,le=25)
    y:float=Field(default=0,ge=-25,le=25)
    z:float=Field(default=0,ge=-25,le=25)

class Material(Strict):
    color:str=Field(default='#a9c4a1',pattern=r'^#[0-9a-fA-F]{6}$')
    opacity:float=Field(default=1,ge=.1,le=1)
    roughness:float=Field(default=.6,ge=0,le=1)
    metalness:float=Field(default=0,ge=0,le=.6)

class Animation(Strict):
    kind:Literal['rotate','orbit','translate','pulse']
    axis:Literal['x','y','z']='y'
    duration:float=Field(default=12,ge=2,le=120)
    radius:float=Field(default=2,ge=.1,le=10)
    target:Vec=Field(default_factory=Vec)
    explanation:str=Field(min_length=5,max_length=500)

class SceneObject(Strict):
    id:str=Field(pattern=r'^[a-zA-Z][a-zA-Z0-9_-]{0,39}$')
    label:str=Field(min_length=1,max_length=70)
    type:Literal['sphere','box','cylinder','cone','torus','line','curve','arrow','bond','particles']
    position:Vec=Field(default_factory=Vec)
    dimensions:Vec=Field(default_factory=lambda:Vec(x=1,y=1,z=1))
    material:Material=Field(default_factory=Material)
    explanation:str=Field(min_length=10,max_length=1500)
    points:list[Vec]=Field(default_factory=list,max_length=12)
    animation:Animation|None=None
    source_ids:list[str]=Field(default_factory=list,max_length=8)
    @model_validator(mode='after')
    def geometry(self):
        if min(self.dimensions.x,self.dimensions.y,self.dimensions.z)<=0 or max(self.dimensions.x,self.dimensions.y,self.dimensions.z)>10:raise ValueError('Dimensions must be positive and at most 10')
        if self.type in ('line','curve','arrow','bond') and len(self.points)<2:raise ValueError('Connections need at least two points')
        return self

class Connection(Strict):
    source:str=Field(max_length=40)
    target:str=Field(max_length=40)
    label:str=Field(max_length=100)
    explanation:str=Field(min_length=5,max_length=600)
    source_ids:list[str]=Field(default_factory=list,max_length=8)

class Step(Strict):
    title:str=Field(min_length=1,max_length=150)
    explanation:str=Field(min_length=5,max_length=1000)
    object_ids:list[str]=Field(min_length=1,max_length=12)
    camera:Vec|None=None

class Challenge(Strict):
    id:str=Field(pattern=r'^[a-zA-Z][a-zA-Z0-9_-]{0,39}$')
    kind:Literal['find','identify','arrange','process','predict','question']
    prompt:str=Field(min_length=5,max_length=500)
    options:list[str]=Field(min_length=2,max_length=12)
    answer:list[str]=Field(min_length=1,max_length=12)
    explanation:str=Field(min_length=5,max_length=800)
    object_ids:list[str]=Field(default_factory=list,max_length=12)
    @model_validator(mode='after')
    def answers(self):
        if len(set(self.options))!=len(self.options) or any(x not in self.options for x in self.answer):raise ValueError('Answers must use unique supplied options')
        if self.kind not in ('arrange','process') and len(self.answer)!=1:raise ValueError('This question expects a single answer')
        return self

class SceneSpec(Strict):
    version:Literal[1]=1
    title:str=Field(min_length=2,max_length=160)
    objectives:list[str]=Field(min_length=1,max_length=6)
    description:str=Field(min_length=10,max_length=2000)
    disclaimer:str=Field(default='Schematic educational illustration, not a physical simulation.',max_length=500)
    camera:Vec=Field(default_factory=lambda:Vec(x=8,y=6,z=12))
    objects:list[SceneObject]=Field(min_length=1,max_length=40)
    connections:list[Connection]=Field(default_factory=list,max_length=60)
    steps:list[Step]=Field(min_length=1,max_length=12)
    challenges:list[Challenge]=Field(min_length=1,max_length=12)
    @model_validator(mode='after')
    def references(self):
        ids={o.id for o in self.objects}
        if len(ids)!=len(self.objects):raise ValueError('Object IDs must be unique')
        if len({c.id for c in self.challenges})!=len(self.challenges):raise ValueError('Challenge IDs must be unique')
        if any(c.source not in ids or c.target not in ids or c.source==c.target for c in self.connections):raise ValueError('Invalid object relationship')
        if any(i not in ids for s in self.steps for i in s.object_ids):raise ValueError('Unknown guided object')
        if any(i not in ids for c in self.challenges for i in c.object_ids):raise ValueError('Unknown challenge object')
        return self
