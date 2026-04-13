# pipeline/core.py
class VideoPipeline:
    def __init__(self, stages):
        self.stages = stages

    def process(self, packet):
        for stage in self.stages:
            packet = stage(packet)
        return packet