from aws_cdk import App
from agent_stack import BedrockAgentsStack

if __name__ == "__main__":
    app = App()
    BedrockAgentsStack(app, "BedrockAgentsStack")
    app.synth()
