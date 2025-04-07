from pathlib import Path
import os

from aws_cdk import CfnOutput, Duration, Stack
from aws_cdk import aws_lambda as _lambda
from aws_cdk import aws_ecr_assets as ecr_assets
from cdklabs.generative_ai_cdk_constructs import bedrock
from constructs import Construct

LAMBDA_CODE_PATH = Path(__file__).parent / "action_handlers"

# Docker on sagemaker has to run on the "sagemaker" network
if os.getenv("SAGEMAKER_APP_TYPE_LOWERCASE") is None:
    NETWORK_NAME = ecr_assets.NetworkMode.default()
else:
    NETWORK_NAME = ecr_assets.NetworkMode.custom("sagemaker")


class BedrockAgentsStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # pandas_layer = _lambda.LayerVersion.from_layer_version_arn(
        #     self,
        #     "PandasLayer",
        #     layer_version_arn=f"arn:aws:lambda:{self.region}:336392948345:layer:AWSSDKPandas-Python311:20",
        # )

        # lxml_layer = _lambda.LayerVersion.from_layer_version_arn(
        #     self,
        #     "LxmlLayer",
        #     layer_version_arn=f"arn:aws:lambda:{self.region}:770693421928:layer:Klayers-p311-lxml:6",
        # )

        # stock_data_layer = _lambda.LayerVersion(
        #     self,
        #     "StockDataLayer",
        #     code=_lambda.Code.from_asset(
        #         (lambda_code_path / "stock_data/layer.zip").as_posix()
        #     ),
        #     compatible_runtimes=[_lambda.Runtime.PYTHON_3_11],
        #     description="Layer for stock data analysis",
        # )

        # Stock Data API Lambda function
        # api_function = _lambda.Function(
        #     self,
        #     "StockDataApiFunction",
        #     runtime=_lambda.Runtime.PYTHON_3_11,
        #     handler="index.lambda_handler",
        #     # code=_lambda.Code.from_asset(
        #     #     (lambda_code_path / "stock_data/package").as_posix()
        #     # ),
        #     code=_lambda.Code.from_asset(
        #         (lambda_code_path / "stock_data/lambda_code").as_posix(),
        #     ),
        #     timeout=Duration.seconds(10),
        #     memory_size=1024,
        #     tracing=_lambda.Tracing.ACTIVE,
        #     environment={
        #         "POWERTOOLS_SERVICE_NAME": "StockDataService",
        #         "POWERTOOLS_LOG_LEVEL": "INFO",
        #     },
        #     description="Agent for Amazon Bedrock handler function",
        #     layers=[stock_data_layer],
        #     # layers=[pandas_layer, lxml_layer],
        # )

        api_function = _lambda.DockerImageFunction(
            self,
            "StockDataApiFunction",
            # runtime=_lambda.Runtime.FROM_IMAGE,
            # handler=_lambda.Handler.FROM_IMAGE,
            # code=_lambda.Code.from_asset(
            #     (lambda_code_path / "stock_data/package").as_posix()
            # ),
            code=_lambda.DockerImageCode.from_image_asset(
                (LAMBDA_CODE_PATH / "stock_data/").as_posix(),
                network_mode=NETWORK_NAME,
            ),
            timeout=Duration.seconds(10),
            memory_size=1024,
            tracing=_lambda.Tracing.ACTIVE,
            environment={
                "POWERTOOLS_SERVICE_NAME": "StockDataService",
                "POWERTOOLS_LOG_LEVEL": "INFO",
            },
            description="Agent for Amazon Bedrock handler function",
        )

        # Cross-Region Inference Profile required to use the Haiku 3.5 model
        cris = bedrock.CrossRegionInferenceProfile.from_config(
            geo_region=bedrock.CrossRegionInferenceProfileRegion.US,
            model=bedrock.BedrockFoundationModel.ANTHROPIC_CLAUDE_3_5_HAIKU_V1_0,
        )

        # Stock Analysis Agent
        agent = bedrock.Agent(
            self,
            "StockAnalysisAgent",
            foundation_model=cris,
            instruction="A research agent that specializes in analyzing stock performance, computing technical indicators, and forecasting volatility.",
            code_interpreter_enabled=True,
            should_prepare_agent=True,
        )

        # Create an action group based on the Stock Data API Lambda function
        stock_analysis_action_group = bedrock.AgentActionGroup(
            name="StockAnalysisActionGroup",
            description="Stock Analysis Action Group",
            executor=bedrock.ActionGroupExecutor.fromlambda_function(api_function),
            enabled=True,
            api_schema=bedrock.ApiSchema.from_local_asset(
                (LAMBDA_CODE_PATH / "stock_data/api_schema.json").as_posix()
            ),
        )

        # Add the action group to the agent
        agent.add_action_group(stock_analysis_action_group)

        CfnOutput(
            self,
            "BedrockAgentArn",
            value=agent.agent_arn,
        )
